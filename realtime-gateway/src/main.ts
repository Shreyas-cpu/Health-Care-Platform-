import http from 'http';

import { config } from './config/env';
import { TeleconsultationGateway } from './gateways/teleconsultation.gateway';
import { PubSubSubscriber } from './redis/pubsub_subscriber';
import { RoomManager } from './services/room_manager';

async function main(): Promise<void> {
  const server = http.createServer((_req, res) => {
    res.writeHead(404);
    res.end();
  });
  const rooms = new RoomManager();
  const pubsub = new PubSubSubscriber(rooms);
  const gateway = new TeleconsultationGateway(server, rooms, pubsub);
  await pubsub.start();

  server.listen(config.PORT, () => console.log(`Real-time gateway listening on :${config.PORT}`));
  const shutdown = async () => {
    await gateway.close();
    await pubsub.close();
    server.close(() => process.exit(0));
  };
  process.once('SIGTERM', shutdown);
  process.once('SIGINT', shutdown);
}

void main().catch((error) => {
  console.error('Unable to start real-time gateway:', error);
  process.exit(1);
});
