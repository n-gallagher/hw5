// The five agents, each dressed as one of the Yale houses: a playful nod to
// Ninth House, not book lore. Lethe, the ninth house, watches the others; here
// the Boss carries its lamp, and the human approver holds the seal.
import type { ReactNode } from "react";
import type { AgentName } from "./api";

export interface House {
  agent: AgentName;
  role: string;     // plain business label: always shown first
  house: string;    // flavor
  craft: string;    // one line on what this agent does at the desk
  color: string;
}

export const HOUSES: Record<AgentName, House> = {
  boss: {
    agent: "boss", role: "Boss", house: "Lethe House",
    craft: "Reads every ticket, sends the work out, makes the final call.", color: "#d9b25f",
  },
  inventory: {
    agent: "inventory", role: "Inventory", house: "Scroll and Key",
    craft: "Opens the stockroom: what's on hand, what's short, who can restock.", color: "#5cc3b4",
  },
  accounting: {
    agent: "accounting", role: "Accounting", house: "Skull and Bones",
    craft: "Reads the ledger's future: cash, invoices, margins, payments for approval.", color: "#e06a5a",
  },
  facilities: {
    agent: "facilities", role: "Facilities", house: "Book and Snake",
    craft: "Keeps the walls standing: the lease, the rent, the due date.", color: "#8fbf72",
  },
  customer_service: {
    agent: "customer_service", role: "Customer Service", house: "Aurelian",
    craft: "Keeps the shop's word: drafts every message, sends none.", color: "#a993e6",
  },
};

export const ORDER: AgentName[] = ["boss", "inventory", "accounting", "facilities", "customer_service"];

export function houseOf(name: string): House | undefined {
  return (HOUSES as Record<string, House>)[name];
}

/** A small engraved sigil per house, drawn in the house color. */
export function Sigil({ agent, size = 34 }: { agent: AgentName; size?: number }) {
  const c = HOUSES[agent].color;
  const ring = <circle cx="20" cy="20" r="18" fill="none" stroke={c} strokeWidth="1.4" opacity="0.9" />;
  const inner = <circle cx="20" cy="20" r="14.5" fill="none" stroke={c} strokeWidth="0.6" opacity="0.5" />;
  const glyph: Record<AgentName, ReactNode> = {
    // Lethe: an open eye that keeps watch
    boss: (
      <g stroke={c} strokeWidth="1.5" fill="none" strokeLinecap="round">
        <path d="M9 20 Q20 10 31 20 Q20 30 9 20 Z" />
        <circle cx="20" cy="20" r="3.6" fill={c} stroke="none" />
      </g>
    ),
    // Scroll and Key: a key
    inventory: (
      <g stroke={c} strokeWidth="1.6" fill="none" strokeLinecap="round">
        <circle cx="14.5" cy="20" r="4.5" />
        <path d="M19 20 H31 M27 20 V24 M30.5 20 V23" />
      </g>
    ),
    // Skull and Bones: crossed bones under a coin
    accounting: (
      <g stroke={c} strokeWidth="1.6" fill="none" strokeLinecap="round">
        <circle cx="20" cy="15" r="4.2" />
        <path d="M12 30 L28 21 M12 21 L28 30" />
      </g>
    ),
    // Book and Snake: an open book with a curling line
    facilities: (
      <g stroke={c} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 14 Q15 12 20 15 Q25 12 30 14 V27 Q25 25 20 28 Q15 25 10 27 Z" />
        <path d="M20 15 V28" />
        <path d="M13 10 q3 -3 6 0 t6 0" opacity="0.8" />
      </g>
    ),
    // Aurelian: a quill
    customer_service: (
      <g stroke={c} strokeWidth="1.5" fill="none" strokeLinecap="round">
        <path d="M28 10 Q17 13 13 28" />
        <path d="M28 10 Q26 20 15 24" />
        <path d="M12 30 L15 26" />
      </g>
    ),
  };
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      {ring}{inner}{glyph[agent]}
    </svg>
  );
}
