import Redis from 'ioredis';

import { config } from '../config/env';
import { RoomManager } from '../services/room_manager';

type RedisClient = Pick<Redis, 'subscribe' | 'publish' | 'quit' | 'disconnect' | 'on'>;

/** Bridges backend Redis events into currently connected WebSocket rooms. */
export class PubSubSubscriber {
  readonly subscriber: RedisClient;
  readonly publisher: RedisClient;
  private started = false;

  constructor(private readonly roomManager: RoomManager, clients?: { subscriber: RedisClient; publisher: RedisClient }) {
    this.subscriber = clients?.subscriber ?? new Redis(config.REDIS_URL);
    this.publisher = clients?.publisher ?? new Redis(config.REDIS_URL);
    // Avoid EventEmitter's fatal unhandled error behaviour; reconnecting is managed by ioredis.
    this.subscriber.on('error', () => undefined);
    this.publisher.on('error', () => undefined);
  }

  async start(): Promise<void> {
    if (this.started) return;
    this.started = true;
    this.subscriber.on('message', (channel: string, message: string) => this.handleMessage(channel, message));
    await this.subscriber.subscribe('appointment:events', 'doctor:presence', 'system:alerts');
  }

  handleMessage(channel: string, message: string): void {
    if (channel !== 'appointment:events') return;
    try {
      const event = JSON.parse(message) as { event_type?: string; data?: Record<string, unknown> };
      if (event.event_type !== 'appointment_status_changed' || !event.data?.appointment_id) return;
      const appointmentId = String(event.data.appointment_id);
      this.roomManager.broadcastToRoom(appointmentId, {
        type: 'appointment_status_changed',
        ...event.data,
      });
    } catch {
      // Invalid external messages must not disrupt the subscription loop.
    }
  }

  async publishChatMessage(appointmentId: string, message: unknown): Promise<void> {
    await this.publisher.publish('appointment:chat', JSON.stringify({ appointment_id: appointmentId, ...(
      typeof message === 'object' && message !== null ? message as object : { message }
    ) }));
  }

  async close(): Promise<void> {
    await Promise.all([this.closeClient(this.subscriber), this.closeClient(this.publisher)]);
  }

  private async closeClient(client: RedisClient): Promise<void> {
    try {
      await client.quit();
    } catch {
      client.disconnect();
    }
  }
}
