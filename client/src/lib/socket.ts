/**
 * Socket.IO client for real-time updates
 */
import { io } from "socket.io-client";

export const socket = io("/", { path: "/ws" });