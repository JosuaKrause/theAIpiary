import { GraphApiProvider } from '../api/graph';
import { ApiVotes, MHash, UserId, Username } from '../api/types';
import { IsGet } from './keys';
import { assertTrue, range, str } from '../misc/util';

export const simpleGraph = (): TestGraph => {
  const graph = new TestGraph(3);
  graph.addLinks([
    ['a', 'b'],
    ['a', 'c'],
    ['a', 'd'],
    ['a', 'e'],
    ['a', 'f'],
    ['g', 'a'],
    ['g', 'b'],
    ['h', 'i'],
    ['h', 'j'],
  ]);
  graph.addTopics(['a', 'h']);
  return graph;
};

export const advancedGraph = (): TestGraph => {
  const graph = new TestGraph(3);
  graph.addLinks([
    ['a1', 'a2'],
    ['a1', 'b2'],
    ['a1', 'c2'],
    ['a1', 'd2'],
    ['a2', 'a3'],
    ['a3', 'a4'],
    ['a3', 'b4'],
    ['a4', 'a5'],
    ['a5', 'a1'],
    ['b4', 'b2'],
    ['b2', 'b4'],
  ]);
  graph.addTopics(['a2', 'b2']);
  return graph;
};

class TestGraph {
  private readonly apiLimit: number;
  private readonly topics: string[];
  private readonly messages: { [key: string]: string };
  private readonly children: { [key: string]: string[] };
  private readonly parents: { [key: string]: string[] };
  private readonly allLinks: [string, string][];

  constructor(apiLimit: number) {
    this.apiLimit = apiLimit;
    this.topics = [];
    this.messages = {};
    this.children = {};
    this.parents = {};
    this.allLinks = [];
  }

  private addTopic(hash: string): void {
    this.addMessage(hash);
    this.topics.push(hash);
  }

  private addMessage(hash: string): void {
    assertTrue(!hash.startsWith('msg:'), `invalid hash: ${hash}`);
    this.messages[hash] = `msg: ${hash}`;
  }

  private addLink(from: string, to: string): void {
    this.addMessage(from);
    this.addMessage(to);
    if (this.children[from] === undefined) {
      this.children[from] = [];
    }
    this.children[from].push(to);
    if (this.parents[to] === undefined) {
      this.parents[to] = [];
    }
    this.parents[to].push(from);
    this.allLinks.push([from, to]);
  }

  addTopics(hashs: string[]): void {
    hashs.forEach((el) => this.addTopic(el));
  }

  addLinks(links: [string, string][]): void {
    links.forEach(([from, to]) => this.addLink(from, to));
  }

  getApiProvider(): GraphApiProvider {
    return {
      topic: async (offset, limit) => {
        const entries: [string, string][] = this.topics
          .slice(offset, offset + Math.min(limit, this.apiLimit))
          .map((el) => [el, this.messages[el]]);
        const endIx = offset + entries.length;
        const next = endIx === this.topics.length ? 0 : endIx;
        return {
          topics: Object.fromEntries(entries),
          next,
        };
      },
      read: async (hashes) => {
        const ms: Readonly<MHash[]> = Array.from(hashes)
          .sort()
          .map((e) => e as MHash);
        const msgArr: string[] = ms.slice(0, this.apiLimit);
        const skipped: Readonly<MHash[]> = ms.slice(this.apiLimit, undefined);
        const messages: Readonly<{ [key: string]: string }> =
          Object.fromEntries(
            msgArr.map((el) => [el, this.messages[el] ?? '[missing]']),
          );
        return { messages, skipped };
      },
      link: async (linkKey, offset, limit, _token) => {
        const { mhash, isGet } = linkKey;
        const map = isGet === IsGet.parent ? this.parents : this.children;
        const arr = map[mhash as MHash] ?? [];
        const ret = arr.slice(offset, offset + Math.min(limit, this.apiLimit));
        const endIx = offset + ret.length;
        const next = endIx === arr.length ? 0 : endIx;
        const links = ret.map((other) => ({
          parent: (isGet === IsGet.parent ? other : mhash) as MHash,
          child: (isGet === IsGet.parent ? mhash : other) as MHash,
          user: 'u/abc' as Username,
          userid: 'abc' as UserId,
          first: 123,
          votes: { up: { count: 1, uservoted: false } },
          meta: 'link',
        }));
        return { links, next };
      },
      userLink: async (userKey, offset, limit, _token) => {
        const { userId } = userKey;
        if (str(userId) !== 'abc') {
          return { links: [], next: 0 };
        }
        const arr = this.allLinks;
        const ret = arr.slice(offset, offset + Math.min(limit, this.apiLimit));
        const endIx = offset + ret.length;
        const next = endIx === arr.length ? 0 : endIx;
        const links = ret.map(([parent, child]) => ({
          parent: parent as MHash,
          child: child as MHash,
          user: `u/${userId}` as Username,
          userid: userId,
          first: 123,
          votes: { up: { count: 1, uservoted: false } },
          meta: 'user',
        }));
        return { links, next };
      },
      singleLink: async (parent, child, _token) => {
        const children = this.children[parent as MHash] ?? [];
        const exists = children.some((cur) => cur === str(child));
        const votes: ApiVotes = exists
          ? { up: { count: 1, uservoted: false } }
          : {};
        return {
          parent,
          child,
          user: exists ? ('u/abc' as Username) : undefined,
          userid: exists ? ('abc' as UserId) : undefined,
          first: exists ? 123 : 999,
          votes,
          meta: 'single',
        };
      },
    };
  }
} // TestGraph

export class InfGraph {
  private readonly apiLimit: number;

  constructor(apiLimit: number) {
    this.apiLimit = apiLimit;
  }

  getApiProvider(): GraphApiProvider {
    return {
      topic: async (offset, limit) => {
        const entries: [string, string][] = range(
          offset,
          offset + Math.min(limit, this.apiLimit),
        ).map((el) => [`a${el}`, `msg: a${el}`]);
        return {
          topics: Object.fromEntries(entries),
          next: offset + entries.length,
        };
      },
      read: async (hashes) => {
        const ms: Readonly<MHash[]> = Array.from(hashes)
          .sort()
          .map((e) => e as MHash);
        const msgArr: string[] = ms.slice(0, this.apiLimit);
        const skipped: Readonly<MHash[]> = ms.slice(this.apiLimit, undefined);
        const messages: Readonly<{ [key: string]: string }> =
          Object.fromEntries(msgArr.map((el) => [el, `msg: ${el}`]));
        return { messages, skipped };
      },
      link: async (linkKey, offset, limit, _token) => {
        const { mhash, isGet } = linkKey;
        const isGetParent = isGet === IsGet.parent;
        const code = mhash.charCodeAt(0);
        const newCode = String.fromCharCode(code + (isGetParent ? -1 : 1));
        const ret = range(offset, offset + Math.min(limit, this.apiLimit));
        const next = offset + ret.length;
        const links = ret.map((other) => ({
          parent: (isGetParent ? `${newCode}${other}` : mhash) as MHash,
          child: (isGetParent ? mhash : `${newCode}${other}`) as MHash,
          user: 'u/abc' as Username,
          userid: 'abc' as UserId,
          first: 123,
          votes: { up: { count: 1, uservoted: false } },
          meta: 'link',
        }));
        return { links, next };
      },
      userLink: async (userKey, offset, limit, _token) => {
        const { userId } = userKey;
        if (str(userId) !== 'abc') {
          return { links: [], next: 0 };
        }
        const arr: [string, string][] = range(
          offset,
          offset + Math.min(limit, this.apiLimit),
        ).map((el) => [`a${el}`, `b${el}`]);
        const ret = arr.slice(offset, offset + Math.min(limit, this.apiLimit));
        const endIx = offset + ret.length;
        const next = endIx === arr.length ? 0 : endIx;
        const links = ret.map(([parent, child]) => ({
          parent: parent as MHash,
          child: child as MHash,
          user: `u/${userId}` as Username,
          userid: userId,
          first: 123,
          votes: { up: { count: 1, uservoted: false } },
          meta: 'user',
        }));
        return { links, next };
      },
      singleLink: async (parent, child, _token) => {
        const pCode = parent.charCodeAt(0);
        const cCode = child.charCodeAt(0);
        const exists = pCode === cCode - 1;
        const votes: ApiVotes = exists
          ? { up: { count: 1, uservoted: false } }
          : {};
        return {
          parent,
          child,
          user: exists ? ('u/abc' as Username) : undefined,
          userid: exists ? ('abc' as UserId) : undefined,
          first: exists ? 123 : 999,
          votes,
          meta: 'single',
        };
      },
    };
  }
} // InfGraph
