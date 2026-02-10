import Link from "next/link";
import { useEffect, useState } from "react";

const DEFAULT_STATUS = "loading...";

export default function Home() {
  const [status, setStatus] = useState<string>(DEFAULT_STATUS);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  useEffect(() => {
    if (!apiUrl) {
      setStatus("missing NEXT_PUBLIC_API_URL");
      return;
    }

    fetch(`${apiUrl}/health`)
      .then((response) => response.json())
      .then((data: { status?: string }) => setStatus(data?.status ?? "unknown"))
      .catch(() => setStatus("unreachable"));
  }, [apiUrl]);

  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem" }}>
      <h1>Manifeed Admin</h1>
      <p>API status: {status}</p>
      <p>
        <Link href="/rss">Open RSS sync page</Link>
      </p>
    </main>
  );
}
