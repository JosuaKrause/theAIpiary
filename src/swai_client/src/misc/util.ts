export function timeout(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export type LoggerCB = (...msg: string[]) => void;

export function maybeLog(
  logger: LoggerCB | undefined,
  text: string,
): LoggerCB {
  return logger !== undefined ? amend(logger, text) : (..._) => undefined;
}

export function amend(logger: LoggerCB, text: string): LoggerCB {
  return (...msg) => logger(text, ...msg);
}

export function num<T extends number>(value: Readonly<T>): number {
  return value as unknown as number;
}

export function str<T extends string>(value: Readonly<T>): Readonly<string> {
  return value as unknown as string;
}

export function range(from: number, to?: number): number[] {
  if (to === undefined) {
    to = from;
    from = 0;
  }
  if (from > to) {
    return [];
  }
  return Array.from(Array(to - from).keys()).map((cur) => from + cur);
}

export function union<K, V>(left: Map<K, V>, right: Map<K, V>): Map<K, V> {
  return new Map(
    Array.from(left.entries()).concat(Array.from(right.entries())),
  );
}

export function detectSlowCallback(
  obj: any,
  onSlow: (e: any) => void,
): () => void {
  let done = false;
  setTimeout(() => {
    if (done) {
      return;
    }
    setTimeout(() => {
      if (done) {
        return;
      }
      const msg = `slow callback detected with: ${debugJSON(obj)}`;
      onSlow(msg);
    }, 900);
  }, 100);
  return () => {
    done = true;
  };
}

/* istanbul ignore next */
export function errHnd(e: any): void {
  if (process.env.JEST_WORKER_ID !== undefined) {
    assertFail(e);
  }
  console.error(e);
}

export function toJson(obj: any): string {
  return JSON.stringify(obj, (_key, value) => {
    if (value instanceof Set) {
      value = Array.from(value.keys());
    }
    return value;
  });
}

const UNITS: readonly [Readonly<string>, number, number][] = [
  ['k', 1000, 1000],
  ['M', 1000, 1000],
];

export function toReadableNumber(num: number): string {
  if (num < 0) {
    return `-${toReadableNumber(-num)}`;
  }
  let unit = '';
  let cur = num;
  let ix = 0;
  while (ix < UNITS.length && cur >= UNITS[ix][2]) {
    const [curUnit, curMul, _] = UNITS[ix];
    unit = curUnit;
    cur /= curMul;
    ix += 1;
  }
  return `${cur.toPrecision(3).replace(/(?:\.0+|(\.\d+?)0+)$/, '$1')}${unit}`;
}

export function assertFail(e: any): never {
  throw new Error(`should not have happened: ${e}`);
}

export function assertTrue(value: boolean, e: any): asserts value {
  if (!value) {
    throw new Error(`assertion was not true: ${e}`);
  }
}

export function assertEqual<T>(
  actual: unknown,
  expected: T,
  name: string,
): asserts actual is T {
  if (actual !== expected) {
    throw new Error(`${name}: actual:${actual} !== expected:${expected}`);
  }
}

export function assertNotEqual(
  actual: unknown,
  expected: unknown,
  name: string,
): void {
  if (actual === expected) {
    throw new Error(`${name}: actual:${actual} === expected:${expected}`);
  }
}

function stringify(obj: any, space: string): string {
  return JSON.stringify(
    obj,
    (_k, value) => {
      if (
        value instanceof Object &&
        !(value instanceof Array) &&
        !(value instanceof Date) &&
        !(value instanceof Function)
      ) {
        value = Object.fromEntries(
          Object.keys(value)
            .sort()
            .map((k) => [k, value[k]])
            .filter(([_k, val]) => val !== undefined),
        );
      }
      return value;
    },
    space,
  );
}

export function debugJSON(obj: any): string {
  return stringify(obj, '  ');
}

export function safeStringify(obj: any): string {
  return stringify(obj, '');
}

export class SafeMap<K, V> {
  private readonly mapValues: Map<string, V>;
  private readonly mapKeys: Map<string, K>;

  constructor(
    entries?: Iterable<readonly [K, V]> | ArrayLike<readonly [K, V]>,
  ) {
    if (entries !== undefined) {
      const es: (readonly [K, V])[] = Array.from(entries);
      this.mapValues = new Map(es.map((e) => [this.key(e[0]), e[1]]));
      this.mapKeys = new Map(es.map((e) => [this.key(e[0]), e[0]]));
    } else {
      this.mapValues = new Map();
      this.mapKeys = new Map();
    }
  }

  private key(key: Readonly<K>): string {
    return safeStringify(key);
  }

  clear(): void {
    this.mapValues.clear();
    this.mapKeys.clear();
  }

  delete(key: Readonly<K>): boolean {
    const k = this.key(key);
    this.mapKeys.delete(k);
    return this.mapValues.delete(k);
  }

  forEach(
    callbackfn: (value: V, key: K, map: this) => void,
    thisArg?: any,
  ): void {
    this.mapValues.forEach((value, key) => {
      const k = this.mapKeys.get(key);
      if (k === undefined) {
        assertTrue(this.mapKeys.has(key), `${key} not in map`);
        const uk = k as K; // NOTE: hack to allow undefined in a key type
        callbackfn.call(thisArg, value, uk, this);
        return;
      }
      callbackfn.call(thisArg, value, k, this);
    }, this);
  }

  get(key: Readonly<K>): V | undefined {
    const k = this.key(key);
    return this.mapValues.get(k);
  }

  has(key: Readonly<K>): boolean {
    const k = this.key(key);
    return this.mapValues.has(k);
  }

  set(key: Readonly<K>, value: V): this {
    const k = this.key(key);
    this.mapKeys.set(k, key);
    this.mapValues.set(k, value);
    return this;
  }

  get size(): number {
    return this.mapValues.size;
  }

  keys(): IterableIterator<K> {
    return this.mapKeys.values();
  }

  values(): IterableIterator<V> {
    return this.mapValues.values();
  }

  entries(): IterableIterator<[K, V]> {
    const res: [K, V][] = Array.from(this.mapValues.entries()).map((entry) => {
      const [key, value] = entry;
      const k = this.mapKeys.get(key);
      if (k === undefined) {
        assertTrue(this.mapKeys.has(key), `${key} not in map`);
        const uk = k as K; // NOTE: hack to allow undefined in a key type
        return [uk, value];
      }
      return [k, value];
    });
    return res.values();
  }
} // SafeMap

export class SafeSet<V> {
  private readonly setValues: Map<string, V>;

  constructor(entries?: Iterable<V> | ArrayLike<V>) {
    if (entries !== undefined) {
      const es: V[] = Array.from(entries);
      this.setValues = new Map(es.map((e) => [this.key(e), e]));
    } else {
      this.setValues = new Map();
    }
  }

  private key(value: Readonly<V>): string {
    return safeStringify(value);
  }

  clear(): void {
    this.setValues.clear();
  }

  delete(value: Readonly<V>): boolean {
    const v = this.key(value);
    return this.setValues.delete(v);
  }

  forEach(
    callbackfn: (value: V, value2: V, set: this) => void,
    thisArg?: any,
  ): void {
    this.setValues.forEach((value) => {
      callbackfn.call(thisArg, value, value, this);
    }, this);
  }

  has(value: Readonly<V>): boolean {
    const v = this.key(value);
    return this.setValues.has(v);
  }

  add(value: V): this {
    const v = this.key(value);
    this.setValues.set(v, value);
    return this;
  }

  get size(): number {
    return this.setValues.size;
  }

  values(): IterableIterator<V> {
    return this.setValues.values();
  }
} // SafeSet
