import { assertEqual, assertNotEqual, assertTrue, SafeMap } from './util';

class LRUEntry<K, V> {
  parent: LRU<K, V>;
  prev: LRUEntry<K, V>;
  next: LRUEntry<K, V>;
  key: K;
  item: V;

  constructor(parent: LRU<K, V>, key: K, item: V) {
    this.parent = parent;
    this.prev = this;
    this.next = this;
    this.key = key;
    this.item = item;
  }
} // LRUEntry

export default class LRU<K, V> {
  private head: LRUEntry<K, V> | undefined;
  private tail: LRUEntry<K, V> | undefined;
  private readonly objs: SafeMap<K, LRUEntry<K, V>>;
  private readonly maxSize: number;

  constructor(maxSize: number) {
    this.maxSize = Math.max(maxSize, 3);
    this.head = undefined;
    this.tail = undefined;
    this.objs = new SafeMap();
  }

  set(key: K, value: V): V | undefined {
    const entry = this.objs.get(key);
    if (entry !== undefined) {
      const res = entry.item;
      entry.item = value;
      this.get(key); // NOTE: this brings the item to the front
      return res;
    }
    const elem = new LRUEntry(this, key, value);
    this.objs.set(key, elem);
    const head = this.head;
    this.head = elem;
    if (head !== undefined) {
      elem.next = head;
      head.prev = elem;
    } else {
      assertTrue(this.tail === undefined, 'tail must be undefined');
      this.tail = elem;
    }
    const tail = this.tail;
    if (tail !== undefined && this.objs.size > this.maxSize) {
      assertEqual(tail.next, tail, 'tail.next <-> tail');
      assertNotEqual(tail.prev, tail, 'tail.prev <-> tail');
      this.tail = tail.prev;
      tail.prev = tail;
      assertEqual(this.tail.next, tail, 'tail.next <-> tail');
      this.tail.next = this.tail;
      this.objs.delete(tail.key);
    }
    return undefined;
  }

  get(key: K): V | undefined {
    const entry = this.objs.get(key);
    if (entry === undefined) {
      return undefined;
    }
    assertTrue(this.head !== undefined, 'head is not set');
    const head = this.head;
    assertEqual(head.prev, head, 'head.prev <-> head');
    if (head !== entry) {
      const prev = entry.prev;
      assertNotEqual(prev, entry, 'prev <-> entry');
      assertEqual(prev.next, entry, 'prev.next <-> entry');
      const next = entry.next;
      if (next === entry) {
        assertEqual(this.tail, entry, 'tail <-> entry');
        this.tail = prev;
        prev.next = prev;
      } else {
        assertEqual(next.prev, entry, 'next.prev <-> entry');
        prev.next = next;
        next.prev = prev;
      }
      entry.prev = entry;
      entry.next = head;
      head.prev = entry;
      this.head = entry;
    }
    return entry.item;
  }

  has(key: K): boolean {
    return this.objs.has(key);
  }

  delete(key: K): void {
    const entry = this.objs.get(key);
    if (entry === undefined) {
      return;
    }
    if (this.head === entry && this.tail === entry) {
      assertEqual(entry.prev, entry, 'entry.prev <-> entry');
      assertEqual(entry.next, entry, 'entry.next <-> entry');
      this.head = undefined;
      this.tail = undefined;
    } else if (this.head === entry) {
      assertEqual(entry.prev, entry, 'entry.prev <-> entry');
      assertNotEqual(entry.next, entry, 'entry.next <-> entry');
      const next = entry.next;
      assertEqual(next.prev, entry, 'next.prev <-> entry');
      next.prev = next;
      this.head = next;
    } else if (this.tail === entry) {
      assertEqual(entry.next, entry, 'entry.next <-> entry');
      assertNotEqual(entry.prev, entry, 'entry.prev <-> entry');
      const prev = entry.prev;
      assertEqual(prev.next, entry, 'prev.next <-> entry');
      prev.next = prev;
      this.tail = prev;
    } else {
      assertNotEqual(entry.next, entry, 'entry.next <-> entry');
      assertNotEqual(entry.prev, entry, 'entry.prev <-> entry');
      const next = entry.next;
      const prev = entry.prev;
      prev.next = next;
      next.prev = prev;
      entry.next = entry;
      entry.prev = entry;
    }
    this.objs.delete(key);
  }

  keys(): K[] {
    let cur = this.head;
    if (cur === undefined) {
      return [];
    }
    const arr: K[] = [];
    while (cur.next !== cur) {
      arr.push(cur.key);
      cur = cur.next;
      assertTrue(
        arr.length <= this.objs.size,
        `${arr.length} <= ${this.objs.size}`,
      );
    }
    arr.push(cur.key);
    return arr;
  }

  values(): V[] {
    let cur = this.head;
    if (cur === undefined) {
      return [];
    }
    const arr: V[] = [];
    while (cur.next !== cur) {
      arr.push(cur.item);
      cur = cur.next;
      assertTrue(
        arr.length <= this.objs.size,
        `${arr.length} <= ${this.objs.size}`,
      );
    }
    arr.push(cur.item);
    return arr;
  }

  clear(): void {
    this.objs.clear();
    this.head = undefined;
    this.tail = undefined;
  }
} // LRU
