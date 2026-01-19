import { NextResponse, type NextRequest } from "next/server";

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { name, email, organization, message } = body ?? {};

  if (!name || typeof name !== "string") {
    return NextResponse.json({ error: "Name is required" }, { status: 400 });
  }

  if (!email || typeof email !== "string" || !emailPattern.test(email)) {
    return NextResponse.json({ error: "Valid email is required" }, { status: 400 });
  }

  const payload = {
    name: name.trim(),
    email: email.trim().toLowerCase(),
    organization: typeof organization === "string" ? organization.trim() : "",
    message: typeof message === "string" ? message.trim() : "",
  };

  await new Promise((resolve) => setTimeout(resolve, 900));

  return NextResponse.json({
    success: true,
    reference: `CG-${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
    receivedAt: new Date().toISOString(),
    ...payload,
  });
}

export async function GET() {
  return NextResponse.json({
    status: "ready",
    message: "Submit a POST request with name, email, organization, and message to join the ChessGuard waitlist.",
  });
}
