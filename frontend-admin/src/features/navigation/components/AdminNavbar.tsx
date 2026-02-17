"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import styles from "./AdminNavbar.module.css";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/rss", label: "RSS" },
  { href: "/sources", label: "Sources" },
];

function isActiveRoute(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AdminNavbar() {
  const pathname = usePathname();

  return (
    <header className={styles.navbar}>
      <div className={styles.inner}>
        <p className={styles.brand}>Manifeed Admin</p>
        <nav className={styles.links} aria-label="Admin navigation">
          {NAV_ITEMS.map((item) => {
            const active = isActiveRoute(pathname, item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={active ? `${styles.link} ${styles.linkActive}` : styles.link}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
