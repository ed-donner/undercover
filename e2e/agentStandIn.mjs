// A stand-in for the agent's service on port 8003, so the end-to-end tests
// never reach the real one. It records every call; GET /calls lists them.
import { createServer } from "node:http";

const calls = [];

createServer((request, response) => {
  if (request.method === "GET" && request.url === "/calls") {
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify(calls));
    return;
  }
  if (request.method === "POST") calls.push(request.url);
  response.statusCode = 202;
  response.end("{}");
}).listen(8003, "127.0.0.1");
