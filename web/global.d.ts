declare module "dns-packet" {
  export const RECURSION_DESIRED: number;
  export function encode(packet: DnsPacket, buf?: Buffer, offset?: number): Buffer;
  export function decode(buf: Buffer, offset?: number): DnsPacket;

  export interface DnsQuestion {
    type: string;
    name: string;
  }

  export interface DnsAnswer {
    type: string;
    name: string;
    ttl?: number;
    data?: unknown;
  }

  export interface DnsPacket {
    type?: "query" | "response";
    id?: number;
    flags?: number;
    rcode?: string | number;
    questions?: DnsQuestion[];
    answers?: DnsAnswer[];
    authorities?: DnsAnswer[];
    additionals?: DnsAnswer[];
  }
}
