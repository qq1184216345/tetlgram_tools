import ports from "../../config/ports.json";

export const BACKEND_HOST = ports.backend.host;
export const BACKEND_PORT = ports.backend.port;
export const API_BASE = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
export const BACKEND_ADDR = `${BACKEND_HOST}:${BACKEND_PORT}`;
