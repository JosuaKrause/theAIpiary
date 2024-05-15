import { MHash, UserId } from '../api/types';
import { assertFail, debugJSON, LoggerCB, maybeLog, str } from '../misc/util';

export function fromMHash(mhash: Readonly<MHash>): Readonly<string> {
  return str(mhash);
}

export type AdjustedLineIndex = number & { _adjustedLineIndex: void };

export function adj(index: number): Readonly<AdjustedLineIndex> {
  return index as AdjustedLineIndex;
}

export enum KeyType {
  invalid = 'invalid',
  topic = 'topic',
  user = 'user',
  userchild = 'userchild',
  link = 'link',
}
export enum IsGet {
  child = 'child',
  parent = 'parent',
}

export interface LinkKey {
  keyType: KeyType.link;
  mhash: Readonly<MHash>;
  isGet: Readonly<IsGet>;
}
interface TopicKey {
  keyType: KeyType.topic;
}
export interface UserKey {
  keyType: KeyType.user;
  userId: Readonly<UserId>;
}
interface UserChildKey {
  keyType: KeyType.userchild;
  parentUser: Readonly<UserId>;
}
interface InvalidKey {
  keyType: KeyType.invalid;
}
export type LineKey = LinkKey | TopicKey | UserKey | UserChildKey | InvalidKey;
export const INVALID_KEY: Readonly<InvalidKey> = { keyType: KeyType.invalid };
export const TOPIC_KEY: Readonly<TopicKey> = { keyType: KeyType.topic };

export enum FullKeyType {
  invalid = 'full-invalid',
  direct = 'full-direct',
  topic = 'full-topic',
  user = 'full-user',
  userchild = 'full-userchild',
  link = 'full-link',
}

export interface FullDirectKey {
  fullKeyType: FullKeyType.direct;
  mhash: Readonly<MHash>;
}
export interface FullLinkKey {
  fullKeyType: FullKeyType.link;
  mhash: Readonly<MHash>;
  isGet: Readonly<IsGet>;
  index: Readonly<AdjustedLineIndex>;
}
export interface FullTopicKey {
  fullKeyType: FullKeyType.topic;
  index: Readonly<AdjustedLineIndex>;
}
interface FullUserKey {
  fullKeyType: FullKeyType.user;
  userId: Readonly<UserId>;
  index: Readonly<AdjustedLineIndex>;
}
interface FullUserChildKey {
  fullKeyType: FullKeyType.userchild;
  parentUser: Readonly<UserId>;
  index: Readonly<AdjustedLineIndex>;
}
interface FullInvalidKey {
  fullKeyType: FullKeyType.invalid;
}
export type FullUserlikeKey = FullUserKey | FullUserChildKey;
export type FullKey =
  | FullDirectKey
  | FullLinkKey
  | FullTopicKey
  | FullUserlikeKey
  | FullInvalidKey;
export type FullIndirectKey =
  | FullLinkKey
  | FullTopicKey
  | FullUserlikeKey
  | FullInvalidKey;
export const INVALID_FULL_KEY: Readonly<FullInvalidKey> = {
  fullKeyType: FullKeyType.invalid,
};

export function asLineKey(
  fullKey: Readonly<FullIndirectKey>,
): Readonly<LineKey> {
  if (fullKey.fullKeyType === FullKeyType.invalid) {
    return INVALID_KEY;
  }
  if (fullKey.fullKeyType === FullKeyType.topic) {
    return TOPIC_KEY;
  }
  if (fullKey.fullKeyType === FullKeyType.user) {
    return { keyType: KeyType.user, userId: fullKey.userId };
  }
  if (fullKey.fullKeyType === FullKeyType.userchild) {
    return { keyType: KeyType.userchild, parentUser: fullKey.parentUser };
  }
  if (fullKey.fullKeyType === FullKeyType.link) {
    const { mhash, isGet } = fullKey;
    return { keyType: KeyType.link, mhash, isGet };
  }
  /* istanbul ignore next */
  assertFail('unreachable');
}

export function toFullKey(
  lineKey: Readonly<LineKey>,
  index: Readonly<AdjustedLineIndex>,
): Readonly<FullIndirectKey> {
  if (lineKey.keyType === KeyType.invalid) {
    return INVALID_FULL_KEY;
  }
  if (lineKey.keyType === KeyType.topic) {
    return { fullKeyType: FullKeyType.topic, index };
  }
  if (lineKey.keyType === KeyType.user) {
    return { fullKeyType: FullKeyType.user, userId: lineKey.userId, index };
  }
  if (lineKey.keyType === KeyType.userchild) {
    return {
      fullKeyType: FullKeyType.userchild,
      parentUser: lineKey.parentUser,
      index,
    };
  }
  if (lineKey.keyType === KeyType.link) {
    const { mhash, isGet } = lineKey;
    return {
      fullKeyType: FullKeyType.link,
      mhash,
      isGet,
      index,
    };
  }
  /* istanbul ignore next */
  assertFail('unreachable');
}

export function asTopicKey(index: number): Readonly<FullIndirectKey> {
  return {
    fullKeyType: FullKeyType.topic,
    index: adj(index),
  };
}

export function asUserKey(
  userId: string,
  index: number,
): Readonly<FullIndirectKey> {
  return {
    fullKeyType: FullKeyType.user,
    userId: userId as UserId,
    index: adj(index),
  };
}

export function asUserChildKey(
  parentUser: string,
  index: number,
): Readonly<FullIndirectKey> {
  return {
    fullKeyType: FullKeyType.userchild,
    parentUser: parentUser as UserId,
    index: adj(index),
  };
}

export function asDirectKey(hash: Readonly<string>): Readonly<FullKey> {
  return {
    fullKeyType: FullKeyType.direct,
    mhash: hash as MHash,
  };
}

export function equalLineKey(
  keyA: Readonly<LineKey>,
  keyB: Readonly<LineKey>,
): boolean {
  if (keyA.keyType !== keyB.keyType) {
    return false;
  }
  if (keyA.keyType === KeyType.invalid && keyB.keyType === KeyType.invalid) {
    return true;
  }
  if (keyA.keyType === KeyType.topic && keyB.keyType === KeyType.topic) {
    return true;
  }
  if (keyA.keyType === KeyType.user && keyB.keyType === KeyType.user) {
    return keyA.userId === keyB.userId;
  }
  if (
    keyA.keyType === KeyType.userchild &&
    keyB.keyType === KeyType.userchild
  ) {
    return keyA.parentUser === keyB.parentUser;
  }
  if (keyA.keyType === KeyType.link && keyB.keyType === KeyType.link) {
    if (keyA.mhash !== keyB.mhash) {
      return false;
    }
    return keyA.isGet === keyB.isGet;
  }
  /* istanbul ignore next */
  assertFail('unreachable');
}

export function equalLineKeys(keysA: LineKey[], keysB: LineKey[]): boolean {
  if (keysA.length !== keysB.length) {
    return false;
  }
  return keysA.reduce((prev, cur, ix) => {
    return prev && equalLineKey(cur, keysB[ix]);
  }, true);
}

export function equalFullKey(
  keyA: Readonly<FullKey>,
  keyB: Readonly<FullKey>,
  logger?: LoggerCB,
): boolean {
  const log = maybeLog(logger, 'equalFullKey:');
  if (keyA.fullKeyType !== keyB.fullKeyType) {
    log(
      `keyA.fullKeyType:${debugJSON(keyA)}`,
      '!==',
      `keyB.fullKeyType:${debugJSON(keyB)}`,
    );
    return false;
  }
  if (
    keyA.fullKeyType === FullKeyType.invalid &&
    keyB.fullKeyType === FullKeyType.invalid
  ) {
    return true;
  }
  if (
    keyA.fullKeyType === FullKeyType.topic &&
    keyB.fullKeyType === FullKeyType.topic
  ) {
    if (keyA.index === keyB.index) {
      return true;
    }
    log(`topic: keyA.index:${keyA.index} !== keyB.index:${keyB.index}`);
    return false;
  }
  if (
    keyA.fullKeyType === FullKeyType.direct &&
    keyB.fullKeyType === FullKeyType.direct
  ) {
    if (keyA.mhash !== keyB.mhash) {
      log(`direct: keyA.mhash:${keyA.mhash} !== keyB.mhash:${keyB.mhash}`);
      return false;
    }
    return true;
  }
  if (
    keyA.fullKeyType === FullKeyType.user &&
    keyB.fullKeyType === FullKeyType.user
  ) {
    if (keyA.userId !== keyB.userId) {
      log(`user: keyA.userId:${keyA.userId} !== keyB.userId:${keyB.userId}`);
      return false;
    }
    if (keyA.index !== keyB.index) {
      log(`user: keyA:${debugJSON(keyA)}`, '!==', `keyB:${debugJSON(keyB)}`);
      return false;
    }
    return true;
  }
  if (
    keyA.fullKeyType === FullKeyType.userchild &&
    keyB.fullKeyType === FullKeyType.userchild
  ) {
    if (keyA.parentUser !== keyB.parentUser) {
      log(
        `userchild: keyA.parentUser:${keyA.parentUser}`,
        '!==',
        `keyB.parentUser:${keyB.parentUser}`,
      );
      return false;
    }
    if (keyA.index !== keyB.index) {
      log(
        `userchild: keyA:${debugJSON(keyA)}`,
        '!==',
        `keyB:${debugJSON(keyB)}`,
      );
      return false;
    }
    return true;
  }
  if (
    keyA.fullKeyType === FullKeyType.link &&
    keyB.fullKeyType === FullKeyType.link
  ) {
    if (keyA.index !== keyB.index) {
      log(
        `keyA.index:${debugJSON(keyA)}`,
        '!==',
        `keyB.index:${debugJSON(keyB)}`,
      );
      return false;
    }
    if (keyA.mhash !== keyB.mhash) {
      log(`keyA.mhash:${keyA.mhash} !== keyB.mhash:${keyB.mhash}`);
      return false;
    }
    if (keyA.isGet !== keyB.isGet) {
      log(`keyA.isGet:${keyA.isGet}`, '!==', `keyB.isGet:${keyB.isGet}`);
      return false;
    }
    return true;
  }
  /* istanbul ignore next */
  assertFail('unreachable');
}
