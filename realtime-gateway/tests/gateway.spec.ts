import http from 'http';
import jwt from 'jsonwebtoken';
import WebSocket from 'ws';

import { config } from '../src/config/env';
import { TeleconsultationGateway } from '../src/gateways/teleconsultation.gateway';
import { PubSubSubscriber } from '../src/redis/pubsub_subscriber';
import { RoomManager } from '../src/services/room_manager';

const appointmentId = 'appointment-phase-05';

class FakePubSub {
  published: Array<{ appointmentId: string; message: unknown }> = [];
  async publishChatMessage(appointmentId: string, message: unknown): Promise<void> {
    this.published.push({ appointmentId, message });
  }
}

const waitForMessage = (socket: WebSocket, type: string): Promise<Record<string, unknown>> => new Promise((resolve, reject) => {
  const timeout = setTimeout(() => reject(new Error(`Timed out waiting for ${type}`)), 3000);
  const listener = (data: WebSocket.RawData) => {
    const message = JSON.parse(data.toString()) as Record<string, unknown>;
    if (message.type === type) {
      clearTimeout(timeout);
      socket.off('message', listener);
      resolve(message);
    }
  };
  socket.on('message', listener);
});

const connect = (port: number, token?: string): Promise<WebSocket> => new Promise((resolve, reject) => {
  const suffix = token ? `?token=${encodeURIComponent(token)}` : '';
  const ws = new WebSocket(`ws://127.0.0.1:${port}/teleconsultation${suffix}`);
  ws.once('open', () => resolve(ws));
  ws.once('error', reject);
});

describe('TeleconsultationGateway', () => {
  let server: http.Server;
  let gateway: TeleconsultationGateway;
  let rooms: RoomManager;
  let pubsub: FakePubSub;
  let port: number;
  const sockets: WebSocket[] = [];

  const token = (userId: string, role: string) => jwt.sign({ sub: userId, role, phone: '+919999999999' }, config.JWT_SECRET_KEY, { algorithm: 'HS256' });

  beforeEach(async () => {
    server = http.createServer();
    rooms = new RoomManager();
    pubsub = new FakePubSub();
    gateway = new TeleconsultationGateway(server, rooms, pubsub);
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(0, '127.0.0.1', resolve);
    });
    port = (server.address() as { port: number }).port;
  });

  afterEach(async () => {
    for (const socket of sockets.splice(0)) socket.terminate();
    if (gateway) await gateway.close();
    if (server?.listening) await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  test('rejects an invalid JWT and accepts a valid JWT handshake', async () => {
    const invalid = await connect(port, 'not-a-jwt');
    sockets.push(invalid);
    await new Promise<void>((resolve) => invalid.once('close', (code) => {
      expect(code).toBe(4001);
      resolve();
    }));

    const patient = await connect(port, token('patient-1', 'patient'));
    sockets.push(patient);
    expect(patient.readyState).toBe(WebSocket.OPEN);
  });

  test('relays WebRTC signal messages between doctor and patient in one room', async () => {
    const doctor = await connect(port, token('doctor-1', 'doctor'));
    const patient = await connect(port, token('patient-1', 'patient'));
    sockets.push(doctor, patient);
    doctor.send(JSON.stringify({ type: 'join_room', appointment_id: appointmentId }));
    await waitForMessage(doctor, 'joined_room');
    const joined = waitForMessage(doctor, 'peer_joined');
    patient.send(JSON.stringify({ type: 'join_room', appointment_id: appointmentId }));
    await waitForMessage(patient, 'joined_room');
    await joined;

    const offer = waitForMessage(patient, 'signal_message');
    doctor.send(JSON.stringify({ type: 'signal_message', appointment_id: appointmentId, data: { type: 'offer', sdp: 'sdp-offer' } }));
    expect(await offer).toMatchObject({ sender_id: 'doctor-1', data: { type: 'offer', sdp: 'sdp-offer' } });
  });

  test('relays in-call chat and publishes a Redis bridge copy', async () => {
    const doctor = await connect(port, token('doctor-1', 'doctor'));
    const patient = await connect(port, token('patient-1', 'patient'));
    sockets.push(doctor, patient);
    doctor.send(JSON.stringify({ type: 'join_room', appointment_id: appointmentId }));
    await waitForMessage(doctor, 'joined_room');
    patient.send(JSON.stringify({ type: 'join_room', appointment_id: appointmentId }));
    await waitForMessage(patient, 'joined_room');

    const chat = waitForMessage(doctor, 'chat_message');
    patient.send(JSON.stringify({ type: 'chat_message', appointment_id: appointmentId, message: 'Hello doctor' }));
    expect(await chat).toMatchObject({ sender_id: 'patient-1', message: 'Hello doctor' });
    await new Promise((resolve) => setImmediate(resolve));
    expect(pubsub.published).toHaveLength(1);
    expect(pubsub.published[0]).toMatchObject({ appointmentId, message: { message: 'Hello doctor' } });
  });

  test('delivers Redis appointment_status_changed events to connected room clients', async () => {
    const patient = await connect(port, token('patient-1', 'patient'));
    sockets.push(patient);
    patient.send(JSON.stringify({ type: 'join_room', appointment_id: appointmentId }));
    await waitForMessage(patient, 'joined_room');

    const bridge = new PubSubSubscriber(rooms, {
      subscriber: { on: jest.fn(), subscribe: jest.fn(), publish: jest.fn(), quit: jest.fn(), disconnect: jest.fn() } as any,
      publisher: { on: jest.fn(), subscribe: jest.fn(), publish: jest.fn(), quit: jest.fn(), disconnect: jest.fn() } as any,
    });
    const update = waitForMessage(patient, 'appointment_status_changed');
    bridge.handleMessage('appointment:events', JSON.stringify({
      event_type: 'appointment_status_changed', data: { appointment_id: appointmentId, status: 'in_progress' },
    }));
    expect(await update).toMatchObject({ appointment_id: appointmentId, status: 'in_progress' });
    await bridge.close();
  });
});
