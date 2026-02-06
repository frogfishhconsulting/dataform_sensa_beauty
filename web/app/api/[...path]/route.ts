import { NextRequest } from "next/server";

function upstreamBase(): string {
  // Server-only env; use docker internal URL in production
  return (
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    "http://localhost:8000"
  );
}

function buildUpstreamUrl(req: NextRequest): URL {
  const base = upstreamBase();
  return new URL(req.nextUrl.pathname + req.nextUrl.search, base);
}

function filteredHeaders(req: NextRequest): Headers {
  const h = new Headers(req.headers);
  // Hop-by-hop headers should not be forwarded
  h.delete("connection");
  h.delete("keep-alive");
  h.delete("proxy-authenticate");
  h.delete("proxy-authorization");
  h.delete("te");
  h.delete("trailers");
  h.delete("transfer-encoding");
  h.delete("upgrade");

  // Let fetch compute content-length
  h.delete("content-length");
  return h;
}

async function proxy(req: NextRequest): Promise<Response> {
  const url = buildUpstreamUrl(req);
  const method = req.method.toUpperCase();

  const upstream = await fetch(url, {
    method,
    headers: filteredHeaders(req),
    // Streaming body for non-GET/HEAD
    body: method === "GET" || method === "HEAD" ? undefined : req.body,
    cache: "no-store",
  });

  const resHeaders = new Headers(upstream.headers);
  // Avoid double-compression issues
  resHeaders.delete("content-encoding");
  return new Response(upstream.body, { status: upstream.status, headers: resHeaders });
}

export async function GET(req: NextRequest) {
  return proxy(req);
}
export async function POST(req: NextRequest) {
  return proxy(req);
}
export async function PUT(req: NextRequest) {
  return proxy(req);
}
export async function PATCH(req: NextRequest) {
  return proxy(req);
}
export async function DELETE(req: NextRequest) {
  return proxy(req);
}

