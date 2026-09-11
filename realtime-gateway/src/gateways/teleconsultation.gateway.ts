import { Server as HttpServer } from 'http';
import WebSocket, { RawData, WebSocketServer } from 'ws';

import { SocketUser, verifySocketAuth } from '../auth/jwt_verifier';
import { PubSubSubscriber } from '../redis/pubsub_subscriber';
import { RoomManager } from '../services/room_manager';

interface GatewayDependencies {
  verifyAuth?: (request: import('http').IncomingMessage) => SocketUser | null;
}

interface ClientMessage {
  type?: string;
  appointment_id?: string;
  data?: unknown;
  message?: string;
  status?: 'waiting' | 'connected' | 'ended';
}

/** WebSocket transport for WebRTC signalling, consultation chat, and call presence. */
export class TeleconsultationGateway {
  readonly wss: WebSocketServer;
  private readonly verifyAuth: (request: import('http').IncomingMessage) => SocketUser | null;

  constructor(
    server: HttpServer,
    private readonly roomManager: RoomManager,
    private readonly pubsub: Pick<PubSubSubscriber, 'publishChatMessage'>,
    dependencies: GatewayDependencies = {},
  ) {
    this.verifyAuth = dependencies.verifyAuth ?? verifySocketAuth;
    this.wss = new WebSocketServer({ server, path: '/teleconsultation' });
    this.wss.on('connection', (ws, request) => this.onConnection(ws, request));
  }

  private onConnection(ws: WebSocket, request: import('http').IncomingMessage): void {
    const user = this.verifyAuth(request);
    if (!user) {
      ws.close(4001, 'Unauthorized');
      return;
    }
    ws.on('message', (raw) => this.onMessage(ws, user, raw));
    ws.on('close', () => this.notifyAndLeave(ws, user));
    ws.on('error', () => undefined);
  }

  private onMessage(ws: WebSocket, user: SocketUser, raw: RawData): void {
    let payload: ClientMessage;
    try {
      payload = JSON.parse(raw.toString()) as ClientMessage;
    } catch {
      this.send(ws, { type: 'error', message: 'Invalid JSON payload' });
      return;
    }
    const appointmentId = payload.appointment_id;

    switch (payload.type) {
      case 'join_room':
        if (!appointmentId) return this.send(ws, { type: 'error', message: 'appointment_id is required' });
        this.roomManager.joinRoom(appointmentId, ws, user);
        this.roomManager.broadcastToRoom(appointmentId, { type: 'peer_joined', user_id: user.userId, role: user.role }, ws);
        return this.send(ws, { type: 'joined_room', appointment_id: appointmentId });
      case 'signal_message':
        if (this.inRoom(ws, appointmentId)) {
          this.roomManager.broadcastToRoom(appointmentId!, { type: 'signal_message', sender_id: user.userId, data: payload.data }, ws);
        }
        return;
      case 'chat_message':
        if (this.inRoom(ws, appointmentId) && typeof payload.message === 'string') {
          const chat = { type: 'chat_message', sender_id: user.userId, role: user.role, message: payload.message, timestamp: new Date().toISOString() };
          this.roomManager.broadcastToRoom(appointmentId!, chat, ws);
          void this.pubsub.publishChatMessage(appointmentId!, chat).catch(() => undefined);
        }
        return;
      case 'call_status':
        if (this.inRoom(ws, appointmentId) && payload.status && ['waiting', 'connected', 'ended'].includes(payload.status)) {
          this.roomManager.broadcastToRoom(appointmentId!, { type: 'call_status', status: payload.status, updated_by: user.userId });
        }
        return;
      case 'leave_room':
        this.notifyAndLeave(ws, user);
        return;
      default:
        this.send(ws, { type: 'error', message: 'Unsupported message type' });
    }
  }

  private inRoom(ws: WebSocket, appointmentId?: string): boolean {
    return Boolean(appointmentId && this.roomManager.getRoom(ws) === appointmentId);
  }

  private notifyAndLeave(ws: WebSocket, user: SocketUser): void {
    const appointmentId = this.roomManager.getRoom(ws);
    if (appointmentId) this.roomManager.broadcastToRoom(appointmentId, { type: 'peer_left', user_id: user.userId }, ws);
    this.roomManager.leaveRoom(ws);
  }

  private send(ws: WebSocket, payload: unknown): void {
    if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
  }

  close(): Promise<void> {
    for (const client of this.wss.clients) client.terminate();
    return new Promise((resolve) => {
      // ws may never invoke its callback if the underlying HTTP server failed to bind.
      const fallback = setTimeout(resolve, 250);
      this.wss.close(() => {
        clearTimeout(fallback);
        resolve();
      });
    });
  }
}
