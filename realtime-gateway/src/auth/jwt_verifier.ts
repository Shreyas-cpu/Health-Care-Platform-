import { IncomingMessage } from 'http';
import jwt, { JwtPayload } from 'jsonwebtoken';

import { config } from '../config/env';

export interface SocketUser {
  userId: string;
  role: string;
  phone?: string;
}

function tokenFromRequest(req: IncomingMessage): string | undefined {
  const host = req.headers.host || 'localhost';
  const fromQuery = new URL(req.url || '/', `http://${host}`).searchParams.get('token');
  if (fromQuery) return fromQuery;

  const authorization = req.headers.authorization;
  if (authorization?.startsWith('Bearer ')) return authorization.slice(7).trim();

  const protocol = req.headers['sec-websocket-protocol'];
  const firstProtocol = Array.isArray(protocol) ? protocol[0] : protocol?.split(',')[0]?.trim();
  return firstProtocol?.startsWith('Bearer ') ? firstProtocol.slice(7).trim() : firstProtocol;
}

/** Validate a WebSocket upgrade credential and return its minimal user context. */
export function verifySocketAuth(req: IncomingMessage): SocketUser | null {
  const token = tokenFromRequest(req);
  if (!token) return null;

  try {
    const decoded = jwt.verify(token, config.JWT_SECRET_KEY, { algorithms: ['HS256'] });
    if (typeof decoded === 'string') return null;
    const payload = decoded as JwtPayload;
    if (typeof payload.sub !== 'string' || typeof payload.role !== 'string') return null;
    return { userId: payload.sub, role: payload.role, phone: typeof payload.phone === 'string' ? payload.phone : undefined };
  } catch {
    return null;
  }
}
