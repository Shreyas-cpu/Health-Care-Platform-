import WebSocket from 'ws';

export interface SocketMeta {
  userId: string;
  role: string;
  appointmentId?: string;
}

/** Owns ephemeral WebSocket membership for active teleconsultation rooms. */
export class RoomManager {
  readonly rooms = new Map<string, Set<WebSocket>>();
  readonly socketMeta = new Map<WebSocket, SocketMeta>();

  joinRoom(appointmentId: string, ws: WebSocket, meta: Omit<SocketMeta, 'appointmentId'>): void {
    this.leaveRoom(ws);
    const room = this.rooms.get(appointmentId) ?? new Set<WebSocket>();
    room.add(ws);
    this.rooms.set(appointmentId, room);
    this.socketMeta.set(ws, { ...meta, appointmentId });
  }

  leaveRoom(ws: WebSocket): string | undefined {
    const meta = this.socketMeta.get(ws);
    const appointmentId = meta?.appointmentId;
    if (appointmentId) {
      const room = this.rooms.get(appointmentId);
      room?.delete(ws);
      if (room?.size === 0) this.rooms.delete(appointmentId);
    }
    this.socketMeta.delete(ws);
    return appointmentId;
  }

  getPeers(appointmentId: string, excludeWs?: WebSocket): WebSocket[] {
    return [...(this.rooms.get(appointmentId) ?? [])].filter(
      (socket) => socket !== excludeWs && socket.readyState === WebSocket.OPEN,
    );
  }

  broadcastToRoom(appointmentId: string, payload: unknown, excludeWs?: WebSocket): void {
    const serialized = JSON.stringify(payload);
    for (const peer of this.getPeers(appointmentId, excludeWs)) peer.send(serialized);
  }

  getRoom(ws: WebSocket): string | undefined {
    return this.socketMeta.get(ws)?.appointmentId;
  }

  getSocketMeta(ws: WebSocket): SocketMeta | undefined {
    return this.socketMeta.get(ws);
  }
}
