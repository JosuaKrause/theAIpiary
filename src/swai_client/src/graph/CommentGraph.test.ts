import CommentGraph, { ContentValueExt } from './CommentGraph';
import {
  adj,
  AdjustedLineIndex,
  asDirectKey,
  asLineKey,
  asTopicKey,
  equalLineKey,
  equalLineKeys,
  FullIndirectKey,
  FullKey,
  FullKeyType,
  INVALID_FULL_KEY,
  INVALID_KEY,
  IsGet,
  KeyType,
  LineKey,
  toFullKey,
  TOPIC_KEY,
} from './keys';
import { advancedGraph, simpleGraph } from './TestGraph';
import {
  assertEqual,
  assertTrue,
  cacheHitProbe,
  debugJSON,
  detectSlowCallback,
  OnCacheMiss,
  range,
} from '../misc/util';
import { Link, MHash, ValidLink } from '../api/types';

function asFullKey(
  hash: Readonly<string>,
  isGetParent: boolean,
  index: number,
): Readonly<FullIndirectKey> {
  return {
    fullKeyType: FullKeyType.link,
    mhash: hash as MHash,
    isGet: isGetParent ? IsGet.parent : IsGet.child,
    index: adj(index),
  };
}

function toLineKey(
  hash: Readonly<string>,
  isGetParent: boolean,
): Readonly<LineKey> {
  return {
    keyType: KeyType.link,
    mhash: hash as MHash,
    isGet: isGetParent ? IsGet.parent : IsGet.child,
  };
}

async function execute<A extends any[], R>(
  fun: (ocm: OnCacheMiss, ...args: A) => Promise<R>,
  args: Readonly<A>,
  callback: (value: R) => void,
  expectCacheMiss: boolean,
): Promise<void> {
  const stack = new Error().stack;
  return new Promise((resolve, reject) => {
    const onErr = (e: any): void => {
      console.warn(stack);
      reject(e);
    };
    const compute = async () => {
      const done = detectSlowCallback(args, onErr);
      const { onCacheMiss, hasCacheMiss } = cacheHitProbe();
      const res = await fun(onCacheMiss, ...args);
      done();
      const hcm = hasCacheMiss();
      assertEqual(hcm, expectCacheMiss, 'hasCacheMiss');
      callback(res);
    };
    compute().then((res) => {
      resolve(res);
    }, onErr);
  });
}

const checkMessage = (
  mhash: string | undefined,
  content?: string,
): ((value: ContentValueExt) => void) => {
  return (value) => {
    const [otherMhash, otherContent] = value;
    if (mhash !== undefined) {
      expect(otherMhash).toEqual(mhash);
    } else {
      expect(otherMhash).toBe(undefined);
    }
    expect(otherContent).toEqual(
      content !== undefined ? content : `msg: ${mhash}`,
    );
  };
};
const checkHash = (
  mhash: string | undefined,
): ((mhash: Readonly<MHash> | undefined) => void) => {
  return (otherMhash) => {
    if (mhash !== undefined) {
      expect(otherMhash).toEqual(mhash);
    } else {
      expect(otherMhash).toBe(undefined);
    }
  };
};
const validLink = (cb: (vlink: ValidLink) => void): ((link: Link) => void) => {
  return (link) => {
    assertTrue(!link.invalid, 'link should be valid');
    cb(link);
  };
};
const checkLink = (parent: string, child: string): ((link: Link) => void) => {
  return validLink((link) => {
    expect(link.parent).toEqual(parent);
    expect(link.child).toEqual(child);
  });
};
const invalidLink = (): ((link: Link) => void) => {
  return (link) => {
    assertTrue(!!link.invalid, 'link should be invalid');
  };
};
const checkNext = (
  lineKey: Readonly<LineKey>,
): ((next: Readonly<LineKey>) => void) => {
  return (child) => {
    assertTrue(
      equalLineKey(child, lineKey),
      `actual: ${debugJSON(child)} expected ${debugJSON(lineKey)}`,
    );
  };
};
const toArgs = (
  fullKey: Readonly<FullIndirectKey>,
  nextIx: number,
): readonly [Readonly<FullIndirectKey>, Readonly<AdjustedLineIndex>] => {
  return [fullKey, nextIx as AdjustedLineIndex];
};

const createGetTopLink = (
  pool: CommentGraph,
): ((
  ocm: OnCacheMiss,
  fullKey: Readonly<FullIndirectKey>,
  parentIndex: Readonly<AdjustedLineIndex>,
) => Promise<Readonly<Link>>) => {
  return (ocm, fullKey, parentIndex) =>
    pool.getTopLink(fullKey, parentIndex, undefined, ocm);
};

const createGetBottomLink = (
  pool: CommentGraph,
): ((
  ocm: OnCacheMiss,
  fullKey: Readonly<FullIndirectKey>,
  childIndex: Readonly<AdjustedLineIndex>,
) => Promise<Readonly<Link>>) => {
  return (ocm, fullKey, childIndex) =>
    pool.getBottomLink(fullKey, childIndex, undefined, ocm);
};

const createGetMessage = (
  pool: CommentGraph,
): ((
  ocm: OnCacheMiss,
  fullKey: Readonly<FullKey>,
) => Promise<Readonly<ContentValueExt>>) => {
  return (ocm, fullKey) => pool.getMessage(fullKey, undefined, ocm);
};

const createGetHash = (
  pool: CommentGraph,
): ((
  ocm: OnCacheMiss,
  fullKey: Readonly<FullKey>,
) => Promise<Readonly<MHash> | undefined>) => {
  return (ocm, fullKey) => pool.getHash(fullKey, undefined, ocm);
};

const createGetParent = (
  pool: CommentGraph,
): ((
  ocm: OnCacheMiss,
  fullKey: Readonly<FullKey>,
) => Promise<Readonly<LineKey>>) => {
  return (ocm, fullKey) => pool.getParent(fullKey, undefined, ocm);
};

const createGetChild = (
  pool: CommentGraph,
): ((
  ocm: OnCacheMiss,
  fullKey: Readonly<FullKey>,
) => Promise<Readonly<LineKey>>) => {
  return (ocm, fullKey) => pool.getChild(fullKey, undefined, ocm);
};

const createCommentGraph = (isSimple: boolean): CommentGraph => {
  return new CommentGraph(
    isSimple
      ? simpleGraph().getApiProvider()
      : advancedGraph().getApiProvider(),
    {
      maxCommentPoolSize: 100,
      maxTopicSize: 100,
      maxLinkPoolSize: 100,
      maxLinkCache: 100,
      maxLineSize: 100,
      maxUserCache: 100,
      maxUserLineSize: 100,
      blockSize: 10,
    },
  );
};

test('simple test comment graph', async () => {
  const pool = createCommentGraph(true);
  const getMessage = createGetMessage(pool);

  await execute(getMessage, [asTopicKey(0)], checkMessage('a'), true);
  await execute(
    getMessage,
    [asTopicKey(1)],
    checkMessage('h', 'msg: h'),
    false,
  );
  await execute(
    getMessage,
    [asTopicKey(-1)],
    checkMessage(undefined, '[unavailable]'),
    false,
  );
  await execute(
    getMessage,
    [asTopicKey(2)],
    checkMessage(undefined, '[unavailable]'),
    false,
  );
  await execute(
    getMessage,
    [asFullKey('a', false, 0)],
    checkMessage('b'),
    true,
  );
  await execute(
    getMessage,
    [asFullKey('a', false, 2)],
    checkMessage('d'),
    true,
  );
  await execute(
    getMessage,
    [asFullKey('a', false, 2)],
    checkMessage('d', 'msg: d'),
    false,
  );
  await execute(
    getMessage,
    [asFullKey('a', false, 4)],
    checkMessage('f'),
    true,
  );
  await execute(
    getMessage,
    [asFullKey('a', false, 5)],
    checkMessage(undefined, '[deleted]'),
    false,
  );
  await execute(
    getMessage,
    [asDirectKey('a')],
    checkMessage('a', 'msg: a'),
    true,
  );
  await execute(
    getMessage,
    [asDirectKey('a')],
    checkMessage('a', 'msg: a'),
    false,
  );
  await execute(
    getMessage,
    [asDirectKey('d')],
    checkMessage('d', 'msg: d'),
    false,
  );
  await execute(
    getMessage,
    [asDirectKey('foo')],
    checkMessage('foo', '[missing]'),
    true,
  );
});

test('get hash graph', async () => {
  const pool = createCommentGraph(true);
  const getHash = createGetHash(pool);

  await execute(getHash, [asTopicKey(1)], checkHash('h'), true);
  await execute(getHash, [asTopicKey(2)], checkHash(undefined), false);
  await execute(getHash, [asDirectKey('foo')], checkHash('foo'), false);
  await execute(getHash, [asFullKey('a', false, 2)], checkHash('d'), true);
  await execute(getHash, [asFullKey('a', true, 0)], checkHash('g'), true);
  await execute(
    getHash,
    [asFullKey('a', true, 1)],
    checkHash(undefined),
    false,
  );
  await execute(getHash, [INVALID_FULL_KEY], checkHash(undefined), false);
});

test('simple bulk message reading', async () => {
  const pool = createCommentGraph(true);
  const getMessage = createGetMessage(pool);

  const hashes = ['b', 'c', 'd', 'e', 'f'];
  const contents = hashes.map((el) => `msg: ${el}`);
  await Promise.all(
    range(5).map((ix) => {
      return execute(
        getMessage,
        [asFullKey('a', false, ix)],
        checkMessage(hashes[ix]),
        true,
      );
    }),
  );
  await Promise.all(
    range(5).map((ix) => {
      return execute(
        getMessage,
        [asFullKey('a', false, ix)],
        checkMessage(hashes[ix], contents[ix]),
        false,
      );
    }),
  );
  await execute(
    getMessage,
    [asFullKey('b', true, 0)],
    checkMessage('a'),
    true,
  );
  await execute(
    getMessage,
    [asFullKey('b', true, 1)],
    checkMessage('g'),
    true,
  );
  await execute(
    getMessage,
    [asFullKey('b', true, 2)],
    checkMessage(undefined, '[deleted]'),
    false,
  );
  pool.clearCache();
  await execute(
    getMessage,
    [asFullKey('b', true, 2)],
    checkMessage(undefined, '[deleted]'),
    true,
  );
  await execute(
    getMessage,
    [INVALID_FULL_KEY],
    checkMessage(undefined, '[invalid]'),
    false,
  );
});

test('topic comment graph', async () => {
  const pool = createCommentGraph(false);
  const getTopLink = createGetTopLink(pool);

  await execute(
    getTopLink,
    toArgs(asTopicKey(0), 0),
    checkLink('a1', 'a2'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asTopicKey(0), 0),
    checkLink('a1', 'a2'),
    false,
  );
  await execute(
    getTopLink,
    toArgs(asTopicKey(1), 0),
    checkLink('a1', 'b2'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asTopicKey(1), 1),
    checkLink('b4', 'b2'),
    false,
  );
  await execute(getTopLink, toArgs(asTopicKey(1), 2), invalidLink(), false);
  await execute(getTopLink, toArgs(asTopicKey(2), 0), invalidLink(), false);
  pool.clearCache();
  await execute(getTopLink, toArgs(asTopicKey(2), 1), invalidLink(), true);
});

test('parent comment graph', async () => {
  const pool = createCommentGraph(false);
  const getTopLink = createGetTopLink(pool);
  await execute(
    getTopLink,
    toArgs(asFullKey('d2', true, 0), 0),
    checkLink('a5', 'a1'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('b4', true, 1), 0),
    checkLink('a1', 'b2'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('b4', true, 1), 1),
    checkLink('b4', 'b2'),
    false,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('b4', true, 0), 0),
    checkLink('a2', 'a3'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('b4', true, 0), 1),
    invalidLink(),
    false,
  );
});

test('cache edge cases for comment graph', async () => {
  const pool = createCommentGraph(false);
  const getTopLink = createGetTopLink(pool);
  const getBottomLink = createGetBottomLink(pool);
  const getMessage = createGetMessage(pool);
  await execute(
    getTopLink,
    toArgs(asFullKey('a4', false, 0), 0),
    checkLink('a4', 'a5'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('a1', false, 1), 0),
    checkLink('a1', 'b2'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('a1', false, 1), 1),
    checkLink('b4', 'b2'),
    false,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('a3', false, 0), 0),
    checkLink('a3', 'a4'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('a3', false, 1), 0),
    checkLink('a3', 'b4'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('a3', false, 1), 1),
    checkLink('b2', 'b4'),
    false,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('b2', false, 0), 0),
    checkLink('a3', 'b4'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('b2', false, 0), 0),
    checkLink('a3', 'b4'),
    false,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('b2', false, 0), 1),
    checkLink('b2', 'b4'),
    false,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('b2', false, 0), 2),
    invalidLink(),
    false,
  );
  pool.clearCache();
  await execute(
    getTopLink,
    toArgs(asFullKey('b2', false, 1), 0),
    invalidLink(),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('b2', false, 1), 0),
    invalidLink(),
    false,
  );
  pool.clearCache();
  await execute(
    getTopLink,
    toArgs(asFullKey('b4', false, 0), 1),
    checkLink('b4', 'b2'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asTopicKey(1), 1),
    checkLink('b4', 'b2'),
    true,
  );
  await execute(
    getTopLink,
    toArgs(asFullKey('a5', true, 0), 0),
    checkLink('a3', 'a4'),
    true,
  );
  await execute(
    getMessage,
    [asFullKey('a4', true, 0)],
    checkMessage('a3'),
    true,
  );
  await execute(
    getMessage,
    [asFullKey('a2', false, 0)],
    checkMessage('a3'),
    true,
  );

  pool.clearCache();
  await execute(
    getBottomLink,
    toArgs(asTopicKey(0), 0),
    checkLink('a2', 'a3'),
    true,
  );
  await execute(
    getBottomLink,
    toArgs(asTopicKey(0), 0),
    checkLink('a2', 'a3'),
    false,
  );
  pool.clearCache();
  await execute(getBottomLink, toArgs(asTopicKey(0), 1), invalidLink(), true);
  await execute(getBottomLink, toArgs(asTopicKey(0), 1), invalidLink(), false);
  await execute(
    getBottomLink,
    toArgs(asTopicKey(1), 0),
    checkLink('b2', 'b4'),
    true,
  );
  pool.clearCache();
  await execute(getMessage, [asTopicKey(1)], checkMessage('b2'), true);
  await execute(
    getBottomLink,
    toArgs(asTopicKey(-1), 0),
    invalidLink(),
    false,
  );
  await execute(getBottomLink, toArgs(asTopicKey(2), 0), invalidLink(), false);
  await execute(getTopLink, toArgs(INVALID_FULL_KEY, 0), invalidLink(), false);
  await execute(
    getBottomLink,
    toArgs(INVALID_FULL_KEY, 0),
    invalidLink(),
    false,
  );
});

test('child comment graph', async () => {
  const pool = createCommentGraph(false);
  const getBottomLink = createGetBottomLink(pool);

  await execute(
    getBottomLink,
    toArgs(asFullKey('a1', false, 1), 0),
    checkLink('b2', 'b4'),
    true,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('b4', true, 1), 0),
    checkLink('b2', 'b4'),
    true,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('b4', true, 0), 0),
    checkLink('a3', 'a4'),
    true,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('b4', true, 0), 1),
    checkLink('a3', 'b4'),
    false,
  );

  pool.clearCache();
  await execute(
    getBottomLink,
    toArgs(asFullKey('a5', false, 0), 0),
    checkLink('a1', 'a2'),
    true,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('a5', false, 0), 1),
    checkLink('a1', 'b2'),
    false,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('a5', false, 0), 2),
    checkLink('a1', 'c2'),
    false,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('a5', false, 0), 3),
    checkLink('a1', 'd2'),
    false,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('a5', false, 0), 4),
    invalidLink(),
    false,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('a5', false, 0), -1),
    invalidLink(),
    true,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('c2', true, 0), 1),
    checkLink('a1', 'b2'),
    true,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('c2', true, 1), 1),
    invalidLink(),
    false,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('c2', true, 0), 2),
    checkLink('a1', 'c2'),
    false,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('a2', false, 0), 0),
    checkLink('a3', 'a4'),
    true,
  );
  await execute(
    getBottomLink,
    toArgs(asFullKey('a2', false, 0), 1),
    checkLink('a3', 'b4'),
    false,
  );
});

test('get parent / child comment graph', async () => {
  const pool = createCommentGraph(false);
  const getParent = createGetParent(pool);
  const getChild = createGetChild(pool);

  await execute(
    getChild,
    [asFullKey('a2', false, 0)],
    checkNext(toLineKey('a3', false)),
    true,
  );
  await execute(
    getChild,
    [asFullKey('c2', true, 0)],
    checkNext(toLineKey('a1', false)),
    true,
  );
  await execute(
    getChild,
    [asFullKey('c2', false, 0)],
    checkNext(INVALID_KEY),
    true,
  );
  await execute(
    getChild,
    [asFullKey('a1', false, 0)],
    checkNext(toLineKey('a2', false)),
    true,
  );
  await execute(
    getChild,
    [asFullKey('a1', false, 1)],
    checkNext(toLineKey('b2', false)),
    false,
  );
  await execute(
    getChild,
    [asFullKey('a1', false, 2)],
    checkNext(toLineKey('c2', false)),
    false,
  );
  await execute(
    getChild,
    [asFullKey('a1', false, 2)],
    checkNext(toLineKey('c2', false)),
    false,
  );
  await execute(
    getChild,
    [asFullKey('a1', false, 4)],
    checkNext(INVALID_KEY),
    false,
  );
  await execute(
    getParent,
    [asFullKey('b2', true, 0)],
    checkNext(toLineKey('a1', true)),
    true,
  );
  await execute(
    getParent,
    [asFullKey('b2', true, 1)],
    checkNext(toLineKey('b4', true)),
    false,
  );
  await execute(
    getChild,
    [asFullKey('b4', true, 0)],
    checkNext(toLineKey('a3', false)),
    true,
  );
  await execute(
    getChild,
    [asFullKey('b4', true, 0)],
    checkNext(toLineKey('a3', false)),
    false,
  );
  await execute(
    getChild,
    [asFullKey('b4', true, 0)],
    checkNext(toLineKey('a3', false)),
    false,
  );
  await execute(
    getParent,
    [asFullKey('a1', false, 1)],
    checkNext(toLineKey('b2', true)),
    false,
  );
  await execute(
    getParent,
    [asFullKey('a1', false, 0)],
    checkNext(toLineKey('a2', true)),
    false,
  );
  await execute(
    getParent,
    [asFullKey('b4', true, 1)],
    checkNext(toLineKey('b2', true)),
    false,
  );
  await execute(
    getParent,
    [asFullKey('b4', true, 0)],
    checkNext(toLineKey('a3', true)),
    false,
  );
  await execute(
    getParent,
    [asFullKey('b4', true, 0)],
    checkNext(toLineKey('a3', true)),
    false,
  );
  await execute(
    getParent,
    [asFullKey('b4', true, 2)],
    checkNext(INVALID_KEY),
    false,
  );
  await execute(
    getChild,
    [asFullKey('b4', true, 1)],
    checkNext(toLineKey('b2', false)),
    false,
  );
  await execute(
    getParent,
    [asDirectKey('a1')],
    checkNext(toLineKey('a1', true)),
    false,
  );
  await execute(
    getChild,
    [asDirectKey('a1')],
    checkNext(toLineKey('a1', false)),
    false,
  );
  await execute(
    getParent,
    [asDirectKey('d2')],
    checkNext(toLineKey('d2', true)),
    false,
  );
  await execute(
    getChild,
    [asDirectKey('d2')],
    checkNext(toLineKey('d2', false)),
    false,
  );
  await execute(
    getParent,
    [asDirectKey('foo')],
    checkNext(toLineKey('foo', true)),
    false,
  );
  await execute(
    getChild,
    [asDirectKey('foo')],
    checkNext(toLineKey('foo', false)),
    false,
  );
});

test('get parent / child of topic', async () => {
  const pool = createCommentGraph(false);
  const getParent = createGetParent(pool);
  const getChild = createGetChild(pool);

  await execute(
    getChild,
    [asTopicKey(0)],
    checkNext(toLineKey('a2', false)),
    true,
  );
  await execute(
    getChild,
    [asTopicKey(1)],
    checkNext(toLineKey('b2', false)),
    false,
  );
  await execute(
    getParent,
    [asTopicKey(0)],
    checkNext(toLineKey('a2', true)),
    false,
  );
  await execute(
    getParent,
    [asTopicKey(1)],
    checkNext(toLineKey('b2', true)),
    false,
  );
  await execute(
    getParent,
    [asTopicKey(1)],
    checkNext(toLineKey('b2', true)),
    false,
  );
  await execute(getParent, [asTopicKey(2)], checkNext(INVALID_KEY), false);
  await execute(getChild, [asTopicKey(-1)], checkNext(INVALID_KEY), false);
  await execute(getChild, [INVALID_FULL_KEY], checkNext(INVALID_KEY), false);
  await execute(getParent, [INVALID_FULL_KEY], checkNext(INVALID_KEY), false);
  pool.clearCache();
  await Promise.all([
    execute(
      getParent,
      [asTopicKey(0)],
      checkNext(toLineKey('a2', true)),
      true,
    ),
    execute(
      getParent,
      [asTopicKey(0)],
      checkNext(toLineKey('a2', true)),
      true,
    ),
    execute(
      getParent,
      [asTopicKey(1)],
      checkNext(toLineKey('b2', true)),
      true,
    ),
    execute(
      getChild,
      [asTopicKey(0)],
      checkNext(toLineKey('a2', false)),
      true,
    ),
    execute(
      getChild,
      [asTopicKey(0)],
      checkNext(toLineKey('a2', false)),
      true,
    ),
    execute(
      getChild,
      [asTopicKey(1)],
      checkNext(toLineKey('b2', false)),
      true,
    ),
  ]);
});

test('line keys', async () => {
  assertTrue(
    equalLineKeys(
      [
        INVALID_KEY,
        TOPIC_KEY,
        { keyType: KeyType.link, mhash: 'a' as MHash, isGet: IsGet.child },
        { keyType: KeyType.link, mhash: 'a' as MHash, isGet: IsGet.parent },
      ],
      [
        { keyType: KeyType.invalid },
        { keyType: KeyType.topic },
        { keyType: KeyType.link, mhash: 'a' as MHash, isGet: IsGet.child },
        { keyType: KeyType.link, mhash: 'a' as MHash, isGet: IsGet.parent },
      ],
    ),
    'equal line keys',
  );
  const comp: [Readonly<LineKey>, Readonly<LineKey>][] = [
    [INVALID_KEY, TOPIC_KEY],
    [
      INVALID_KEY,
      { keyType: KeyType.link, mhash: 'a' as MHash, isGet: IsGet.child },
    ],
    [TOPIC_KEY, INVALID_KEY],
    [
      TOPIC_KEY,
      { keyType: KeyType.link, mhash: 'a' as MHash, isGet: IsGet.child },
    ],
    [toLineKey('a', false), toLineKey('a', true)],
    [toLineKey('a', true), toLineKey('a', false)],
    [toLineKey('b', false), toLineKey('a', false)],
    [toLineKey('b', true), toLineKey('a', true)],
    [toLineKey('c', false), toLineKey('a', true)],
    [toLineKey('c', true), toLineKey('a', false)],
  ];
  assertTrue(
    comp.every((cur) => {
      const [a, b] = cur;
      return !equalLineKey(a, b);
    }),
    'unequal line keys',
  );
  assertTrue(!equalLineKeys([], [INVALID_KEY]), 'mismatching length');
  assertTrue(!equalLineKeys([TOPIC_KEY], [INVALID_KEY]), 'unequal static');
  expect(toFullKey(toLineKey('a', true), -1 as AdjustedLineIndex)).toEqual(
    asFullKey('a', true, -1),
  );
  expect(toFullKey(toLineKey('a', false), 0 as AdjustedLineIndex)).toEqual(
    asFullKey('a', false, 0),
  );
  expect(toFullKey(toLineKey('c', true), 3 as AdjustedLineIndex)).toEqual(
    asFullKey('c', true, 3),
  );
  expect(toFullKey(TOPIC_KEY, -1 as AdjustedLineIndex)).toEqual(
    asTopicKey(-1),
  );
  expect(toFullKey(TOPIC_KEY, 5 as AdjustedLineIndex)).toEqual(asTopicKey(5));
  expect(toFullKey(TOPIC_KEY, 0 as AdjustedLineIndex)).toEqual(asTopicKey(0));
  expect(toFullKey(INVALID_KEY, 2 as AdjustedLineIndex)).toEqual(
    INVALID_FULL_KEY,
  );
  expect(
    asLineKey(toFullKey(toLineKey('f', false), 4 as AdjustedLineIndex)),
  ).toEqual(toLineKey('f', false));
  expect(
    asLineKey(toFullKey(toLineKey('g', true), 0 as AdjustedLineIndex)),
  ).toEqual(toLineKey('g', true));
  expect(asLineKey(toFullKey(TOPIC_KEY, 5 as AdjustedLineIndex))).toEqual(
    TOPIC_KEY,
  );
  expect(asLineKey(toFullKey(INVALID_KEY, 6 as AdjustedLineIndex))).toEqual(
    INVALID_KEY,
  );
});
