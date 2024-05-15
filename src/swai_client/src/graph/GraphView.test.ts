import CommentGraph from './CommentGraph';
import {
  Cell,
  consistentLinks,
  equalView,
  GraphView,
  HDirection,
  initUserView,
  initView,
  progressView,
  scrollBottomHorizontal,
  scrollTopHorizontal,
  scrollVertical,
  VDirection,
} from './GraphView';
import {
  adj,
  asDirectKey,
  asTopicKey,
  asUserChildKey,
  asUserKey,
  FullIndirectKey,
  FullKey,
  FullKeyType,
  INVALID_FULL_KEY,
  IsGet,
} from './keys';
import { advancedGraph, InfGraph } from './TestGraph';
import {
  assertTrue,
  debugJSON,
  detectSlowCallback,
  LoggerCB,
} from '../misc/util';
import { INVALID_LINK, MHash, UserId } from '../api/types';

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

const RERUN_ON_ERROR = true;

async function execute(
  graph: CommentGraph,
  view: Readonly<GraphView> | undefined,
  expected: Readonly<GraphView>,
  expectedTransitions: number,
): Promise<Readonly<GraphView>> {
  const stack = new Error().stack;

  const process = (
    resolve: (
      value: Readonly<GraphView> | PromiseLike<Readonly<GraphView>>,
    ) => void,
    onErr: (reason: any, transitionCount: number) => void,
    logger: LoggerCB | undefined,
  ): void => {
    let transitionCount = 0;
    assertTrue(view !== undefined, 'view is not set');

    const transition: (
      view: Readonly<GraphView>,
    ) => Promise<Readonly<GraphView>> = async (oldView) => {
      const done = detectSlowCallback(oldView, (e) => {
        onErr(e, transitionCount);
      });
      const { view, change } = await progressView(
        graph,
        oldView,
        undefined,
        undefined,
        logger,
      );
      done();
      if (change) {
        transitionCount += 1;
        return transition(view);
      }
      if (transitionCount !== expectedTransitions) {
        throw new Error(
          `${transitionCount} !== expected ${expectedTransitions}`,
        );
      }
      if (
        equalView(view, expected, console.warn) &&
        consistentLinks(view, console.warn)
      ) {
        return view;
      }
      throw new Error(
        `${debugJSON(view)}\n!==\nexpected ${debugJSON(expected)}`,
      );
    };
    transition(view).then(resolve, (e) => {
      onErr(e, transitionCount);
    });
  };

  return new Promise((resolve, reject) => {
    const onErr = (e: any, transitionCount: number): void => {
      console.group('rerun');
      const afterRerun = () => {
        console.groupEnd();
        console.log(`error after ${transitionCount} transitions`, stack);
        reject(e);
      };
      if (RERUN_ON_ERROR) {
        process(afterRerun, afterRerun, console.log);
      } else {
        console.log(
          'set RERUN_ON_ERROR to true to get a detailed replay.',
          'note, that caching behavior might be different in the rerun',
        );
        afterRerun();
      }
    };
    process(resolve, onErr, undefined);
  });
}

function cellFromString(key: string, fullKey: FullKey): Cell {
  return {
    fullKey,
    mhash: key as MHash,
    content: `msg: ${key}`,
  };
}

function invalidCell(): Cell {
  return {
    invalid: true,
    fullKey: INVALID_FULL_KEY,
    content: '[invalid]',
    topLink: INVALID_LINK,
  };
}

function buildFullView(
  top: [string, FullKey] | undefined,
  middleTop: [
    [string, FullKey] | undefined,
    [string, FullKey],
    [string, FullKey] | undefined,
  ],
  middleBottom: [
    [string, FullKey] | undefined,
    [string, FullKey],
    [string, FullKey] | undefined,
  ],
  bottom: [string, FullKey] | undefined,
  topSkip: string | undefined,
  bottomSkip: string | undefined,
): Readonly<GraphView> {
  return {
    top: top !== undefined ? cellFromString(...top) : invalidCell(),
    topLeft:
      middleTop[0] !== undefined
        ? cellFromString(...middleTop[0])
        : invalidCell(),
    centerTop: cellFromString(...middleTop[1]),
    topRight:
      middleTop[2] !== undefined
        ? cellFromString(...middleTop[2])
        : invalidCell(),
    bottomLeft:
      middleBottom[0] !== undefined
        ? cellFromString(...middleBottom[0])
        : invalidCell(),
    centerBottom: cellFromString(...middleBottom[1]),
    bottomRight:
      middleBottom[2] !== undefined
        ? cellFromString(...middleBottom[2])
        : invalidCell(),
    bottom: bottom !== undefined ? cellFromString(...bottom) : invalidCell(),
    topSkip: topSkip !== undefined ? (topSkip as MHash) : undefined,
    bottomSkip: bottomSkip !== undefined ? (bottomSkip as MHash) : undefined,
  };
}

test('test graph view init', async () => {
  const graph = new CommentGraph(advancedGraph().getApiProvider(), {
    maxCommentPoolSize: 100,
    maxTopicSize: 100,
    maxLinkPoolSize: 100,
    maxLinkCache: 100,
    maxLineSize: 100,
    maxUserCache: 100,
    maxUserLineSize: 100,
    blockSize: 10,
  });

  const initGraph = await execute(
    graph,
    initView(undefined),
    buildFullView(
      ['a1', asFullKey('a2', true, 0)],
      [undefined, ['a2', asTopicKey(0)], ['b2', asTopicKey(1)]],
      [undefined, ['a3', asFullKey('a2', false, 0)], undefined],
      ['a4', asFullKey('a3', false, 0)],
      undefined,
      undefined,
    ),
    13,
  );
  assertTrue(initGraph !== undefined, 'initGraph is undefined');

  const { view: invalidView, change: invalidChange } = await progressView(
    graph,
    { centerTop: invalidCell() },
    undefined,
  );
  assertTrue(!invalidChange, 'no change allowed for invalid');
  assertTrue(
    equalView(invalidView, { centerTop: invalidCell() }),
    'should be invalid',
  );

  assertTrue(
    scrollTopHorizontal(initGraph, HDirection.Left) === undefined,
    `${debugJSON(scrollTopHorizontal(initGraph, HDirection.Left))}`,
  );
  assertTrue(
    scrollBottomHorizontal(initGraph, HDirection.Left) === undefined,
    `${debugJSON(scrollBottomHorizontal(initGraph, HDirection.Left))}`,
  );
  assertTrue(
    scrollBottomHorizontal(initGraph, HDirection.Right) === undefined,
    `${debugJSON(scrollBottomHorizontal(initGraph, HDirection.Right))}`,
  );

  await execute(
    graph,
    scrollTopHorizontal(initGraph, HDirection.Right),
    buildFullView(
      ['a1', asFullKey('b2', true, 0)],
      [['a2', asTopicKey(0)], ['b2', asTopicKey(1)], undefined],
      [undefined, ['b4', asFullKey('b2', false, 0)], undefined],
      ['b2', asFullKey('b4', false, 0)],
      undefined,
      undefined,
    ),
    11,
  );
  const a1Graph = await execute(
    graph,
    initView('a1' as MHash),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], undefined],
      [
        undefined,
        ['a2', asFullKey('a1', false, 0)],
        ['b2', asFullKey('a1', false, 1)],
      ],
      ['a3', asFullKey('a2', false, 0)],
      'a1',
      undefined,
    ),
    13,
  );

  assertTrue(a1Graph !== undefined, 'a1Graph is undefined');
  assertTrue(
    scrollTopHorizontal(a1Graph, HDirection.Left) === undefined,
    `${debugJSON(scrollTopHorizontal(a1Graph, HDirection.Left))}`,
  );
  assertTrue(
    scrollBottomHorizontal(a1Graph, HDirection.Left) === undefined,
    `${debugJSON(scrollBottomHorizontal(a1Graph, HDirection.Left))}`,
  );

  const a1BRGraph = await execute(
    graph,
    scrollBottomHorizontal(a1Graph, HDirection.Right),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], ['b4', asFullKey('b2', true, 1)]],
      [
        ['a2', asFullKey('a1', false, 0)],
        ['b2', asFullKey('a1', false, 1)],
        ['c2', asFullKey('a1', false, 2)],
      ],
      ['b4', asFullKey('b2', false, 0)],
      'a1',
      undefined,
    ),
    6,
  );

  const a1BRBRGraph = await execute(
    graph,
    scrollBottomHorizontal(a1BRGraph, HDirection.Right),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], undefined],
      [
        ['b2', asFullKey('a1', false, 1)],
        ['c2', asFullKey('a1', false, 2)],
        ['d2', asFullKey('a1', false, 3)],
      ],
      undefined,
      'a1',
      undefined,
    ),
    6,
  );

  assertTrue(
    scrollVertical(a1BRBRGraph, VDirection.Down) === undefined,
    `${debugJSON(scrollVertical(a1BRBRGraph, VDirection.Down))}`,
  );

  await execute(
    graph,
    scrollBottomHorizontal(a1BRGraph, HDirection.Left),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], undefined],
      [
        undefined,
        ['a2', asFullKey('a1', false, 0)],
        ['b2', asFullKey('a1', false, 1)],
      ],
      ['a3', asFullKey('a2', false, 0)],
      'a1',
      undefined,
    ),
    6,
  );

  const a1BRTRGraph = await execute(
    graph,
    scrollTopHorizontal(a1BRGraph, HDirection.Right),
    buildFullView(
      ['a3', asFullKey('b4', true, 0)],
      [['a1', asDirectKey('a1')], ['b4', asFullKey('b2', true, 1)], undefined],
      [undefined, ['b2', asDirectKey('b2')], undefined],
      ['b4', asFullKey('b2', false, 0)],
      'a1',
      'b2',
    ),
    8,
  );

  const a1BRTRUGraph = await execute(
    graph,
    scrollVertical(a1BRTRGraph, VDirection.Up),
    buildFullView(
      ['a2', asFullKey('a3', true, 0)],
      [
        undefined,
        ['a3', asFullKey('b4', true, 0)],
        ['b2', asFullKey('b4', true, 1)],
      ],
      [['a1', asDirectKey('a1')], ['b4', asFullKey('b2', true, 1)], undefined],
      ['b2', asDirectKey('b2')],
      undefined,
      'a1',
    ),
    6,
  );

  const a1BRTRUTRGraph = await execute(
    graph,
    scrollTopHorizontal(a1BRTRUGraph, HDirection.Right),
    buildFullView(
      ['a1', asFullKey('b2', true, 0)],
      [
        ['a3', asFullKey('b4', true, 0)],
        ['b2', asFullKey('b4', true, 1)],
        undefined,
      ],
      [undefined, ['b4', asDirectKey('b4')], undefined],
      ['b2', asDirectKey('b2')],
      undefined,
      'b4',
    ),
    8,
  );

  await execute(
    graph,
    scrollVertical(a1BRTRUTRGraph, VDirection.Down),
    buildFullView(
      ['b2', asFullKey('b4', true, 1)],
      [undefined, ['b4', asDirectKey('b4')], undefined],
      [undefined, ['b2', asDirectKey('b2')], undefined],
      ['b4', asFullKey('b2', false, 0)],
      'b4',
      'b2',
    ),
    6,
  );

  const a1BRTRUTRTLGraph = await execute(
    graph,
    scrollTopHorizontal(a1BRTRUTRGraph, HDirection.Left),
    buildFullView(
      ['a2', asFullKey('a3', true, 0)],
      [
        undefined,
        ['a3', asFullKey('b4', true, 0)],
        ['b2', asFullKey('b4', true, 1)],
      ],
      [
        undefined,
        ['b4', asDirectKey('b4')],
        ['a4', asFullKey('a3', false, 0)],
      ],
      ['b2', asDirectKey('b2')],
      undefined,
      'b4',
    ),
    8,
  );

  const a1BRTRUTRTLBRGraph = await execute(
    graph,
    scrollBottomHorizontal(a1BRTRUTRTLGraph, HDirection.Right),
    buildFullView(
      ['a2', asFullKey('a3', true, 0)],
      [undefined, ['a3', asDirectKey('a3')], undefined],
      [
        ['b4', asDirectKey('b4')],
        ['a4', asFullKey('a3', false, 0)],
        undefined,
      ],
      ['a5', asFullKey('a4', false, 0)],
      'a3',
      'b4',
    ),
    6,
  );

  assertTrue(
    scrollTopHorizontal(a1BRTRUTRTLBRGraph, HDirection.Right) === undefined,
    `${debugJSON(scrollTopHorizontal(a1BRTRUTRTLBRGraph, HDirection.Right))}`,
  );

  await execute(
    graph,
    initView('a5' as MHash, 'a1' as MHash),
    buildFullView(
      ['a4', asFullKey('a5', true, 0)],
      [undefined, ['a5', asDirectKey('a5')], undefined],
      [undefined, ['a1', asDirectKey('a1')], undefined],
      ['a2', asFullKey('a1', false, 0)],
      'a5',
      'a1',
    ),
    13,
  );
});

test('test graph infinite', async () => {
  const graph = new CommentGraph(new InfGraph(3).getApiProvider(), {
    maxCommentPoolSize: 100,
    maxTopicSize: 100,
    maxLinkPoolSize: 100,
    maxLinkCache: 100,
    maxLineSize: 100,
    maxUserCache: 100,
    maxUserLineSize: 100,
    blockSize: 10,
  });

  const v1 = await execute(
    graph,
    initView(undefined),
    buildFullView(
      ['`0', asFullKey('a0', true, 0)],
      [undefined, ['a0', asTopicKey(0)], ['a1', asTopicKey(1)]],
      [
        undefined,
        ['b0', asFullKey('a0', false, 0)],
        ['b1', asFullKey('a0', false, 1)],
      ],
      ['c0', asFullKey('b0', false, 0)],
      undefined,
      undefined,
    ),
    13,
  );
  const v2 = await execute(
    graph,
    scrollBottomHorizontal(v1, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a0', true, 0)],
      [undefined, ['a0', asDirectKey('a0')], ['a1', asFullKey('b1', true, 1)]],
      [
        ['b0', asFullKey('a0', false, 0)],
        ['b1', asFullKey('a0', false, 1)],
        ['b2', asFullKey('a0', false, 2)],
      ],
      ['c0', asFullKey('b1', false, 0)],
      'a0',
      undefined,
    ),
    6,
  );
  const v3 = await execute(
    graph,
    scrollBottomHorizontal(v2, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a0', true, 0)],
      [undefined, ['a0', asDirectKey('a0')], ['a1', asFullKey('b2', true, 1)]],
      [
        ['b1', asFullKey('a0', false, 1)],
        ['b2', asFullKey('a0', false, 2)],
        ['b3', asFullKey('a0', false, 3)],
      ],
      ['c0', asFullKey('b2', false, 0)],
      'a0',
      undefined,
    ),
    6,
  );
  const v4 = await execute(
    graph,
    scrollBottomHorizontal(v3, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a0', true, 0)],
      [undefined, ['a0', asDirectKey('a0')], ['a1', asFullKey('b3', true, 1)]],
      [
        ['b2', asFullKey('a0', false, 2)],
        ['b3', asFullKey('a0', false, 3)],
        ['b4', asFullKey('a0', false, 4)],
      ],
      ['c0', asFullKey('b3', false, 0)],
      'a0',
      undefined,
    ),
    6,
  );
  const v5 = await execute(
    graph,
    scrollTopHorizontal(v4, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a1', true, 0)],
      [
        ['a0', asDirectKey('a0')],
        ['a1', asFullKey('b3', true, 1)],
        ['a2', asFullKey('b3', true, 2)],
      ],
      [
        undefined,
        ['b3', asDirectKey('b3')],
        ['b0', asFullKey('a1', false, 0)],
      ],
      ['c0', asFullKey('b3', false, 0)],
      'a0',
      'b3',
    ),
    8,
  );
  const v6 = await execute(
    graph,
    scrollBottomHorizontal(v5, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], ['a0', asFullKey('b0', true, 0)]],
      [
        ['b3', asDirectKey('b3')],
        ['b0', asFullKey('a1', false, 0)],
        ['b1', asFullKey('a1', false, 1)],
      ],
      ['c0', asFullKey('b0', false, 0)],
      'a1',
      'b3',
    ),
    6,
  );
  const v7 = await execute(
    graph,
    scrollBottomHorizontal(v6, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], ['a0', asFullKey('b1', true, 0)]],
      [
        ['b0', asFullKey('a1', false, 0)],
        ['b1', asFullKey('a1', false, 1)],
        ['b2', asFullKey('a1', false, 2)],
      ],
      ['c0', asFullKey('b1', false, 0)],
      'a1',
      'b3',
    ),
    6,
  );
  const v8 = await execute(
    graph,
    scrollBottomHorizontal(v7, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], ['a0', asFullKey('b2', true, 0)]],
      [
        ['b1', asFullKey('a1', false, 1)],
        ['b2', asFullKey('a1', false, 2)],
        ['b4', asFullKey('a1', false, 4)],
      ],
      ['c0', asFullKey('b2', false, 0)],
      'a1',
      'b3',
    ),
    6,
  );
  const v9 = await execute(
    graph,
    scrollBottomHorizontal(v8, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], ['a0', asFullKey('b4', true, 0)]],
      [
        ['b2', asFullKey('a1', false, 2)],
        ['b4', asFullKey('a1', false, 4)],
        ['b5', asFullKey('a1', false, 5)],
      ],
      ['c0', asFullKey('b4', false, 0)],
      'a1',
      'b3',
    ),
    6,
  );
  const v10 = await execute(
    graph,
    scrollBottomHorizontal(v9, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], ['a0', asFullKey('b5', true, 0)]],
      [
        ['b4', asFullKey('a1', false, 4)],
        ['b5', asFullKey('a1', false, 5)],
        ['b6', asFullKey('a1', false, 6)],
      ],
      ['c0', asFullKey('b5', false, 0)],
      'a1',
      'b3',
    ),
    6,
  );

  await execute(graph, scrollBottomHorizontal(v10, HDirection.Left), v9, 6);
  await execute(graph, scrollBottomHorizontal(v9, HDirection.Left), v8, 6);
  await execute(graph, scrollBottomHorizontal(v8, HDirection.Left), v7, 6);
  await execute(graph, scrollBottomHorizontal(v7, HDirection.Left), v6, 6);

  const v11 = await execute(
    graph,
    scrollBottomHorizontal(v6, HDirection.Left),
    buildFullView(
      ['`0', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], ['a0', asFullKey('b3', true, 0)]],
      [
        undefined,
        ['b3', asDirectKey('b3')],
        ['b0', asFullKey('a1', false, 0)],
      ],
      ['c0', asFullKey('b3', false, 0)],
      'a1',
      'b3',
    ),
    6,
  );

  assertTrue(
    scrollBottomHorizontal(v11, HDirection.Left) === undefined,
    `${debugJSON(scrollBottomHorizontal(v11, HDirection.Left))}`,
  );

  const v12 = await execute(
    graph,
    scrollTopHorizontal(v11, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a0', true, 0)],
      [
        ['a1', asDirectKey('a1')],
        ['a0', asFullKey('b3', true, 0)],
        ['a2', asFullKey('b3', true, 2)],
      ],
      [
        undefined,
        ['b3', asDirectKey('b3')],
        ['b0', asFullKey('a0', false, 0)],
      ],
      ['c0', asFullKey('b3', false, 0)],
      'a1',
      'b3',
    ),
    8,
  );
  const v13 = await execute(
    graph,
    scrollTopHorizontal(v12, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a2', true, 0)],
      [
        ['a0', asFullKey('b3', true, 0)],
        ['a2', asFullKey('b3', true, 2)],
        ['a3', asFullKey('b3', true, 3)],
      ],
      [
        undefined,
        ['b3', asDirectKey('b3')],
        ['b0', asFullKey('a2', false, 0)],
      ],
      ['c0', asFullKey('b3', false, 0)],
      'a1',
      'b3',
    ),
    8,
  );
  const v14 = await execute(
    graph,
    scrollTopHorizontal(v13, HDirection.Right),
    buildFullView(
      ['`0', asFullKey('a3', true, 0)],
      [
        ['a2', asFullKey('b3', true, 2)],
        ['a3', asFullKey('b3', true, 3)],
        ['a4', asFullKey('b3', true, 4)],
      ],
      [
        undefined,
        ['b3', asDirectKey('b3')],
        ['b0', asFullKey('a3', false, 0)],
      ],
      ['c0', asFullKey('b3', false, 0)],
      'a1',
      'b3',
    ),
    8,
  );

  await execute(graph, scrollTopHorizontal(v14, HDirection.Left), v13, 8);
  await execute(graph, scrollTopHorizontal(v13, HDirection.Left), v12, 8);
  await execute(graph, scrollTopHorizontal(v12, HDirection.Left), v11, 8);

  assertTrue(
    scrollTopHorizontal(v11, HDirection.Left) === undefined,
    `${debugJSON(scrollTopHorizontal(v11, HDirection.Left))}`,
  );
  assertTrue(
    scrollBottomHorizontal(v14, HDirection.Left) === undefined,
    `${debugJSON(scrollBottomHorizontal(v14, HDirection.Left))}`,
  );
});

test('test user graph', async () => {
  const graph = new CommentGraph(advancedGraph().getApiProvider(), {
    maxCommentPoolSize: 100,
    maxTopicSize: 100,
    maxLinkPoolSize: 100,
    maxLinkCache: 100,
    maxLineSize: 100,
    maxUserCache: 100,
    maxUserLineSize: 100,
    blockSize: 10,
  });
  const v0 = await execute(
    graph,
    initUserView('abc' as UserId),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [undefined, ['a1', asUserKey('abc', 0)], ['a1', asUserKey('abc', 1)]],
      [
        undefined,
        ['a2', asUserChildKey('abc', 0)],
        ['b2', asFullKey('a1', false, 1)],
      ],
      ['a3', asFullKey('a2', false, 0)],
      undefined,
      'a2',
    ),
    13,
  );
  const v1 = await execute(
    graph,
    scrollTopHorizontal(v0, HDirection.Right),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [
        ['a1', asUserKey('abc', 0)],
        ['a1', asUserKey('abc', 1)],
        ['a1', asUserKey('abc', 2)],
      ],
      [
        undefined,
        ['b2', asUserChildKey('abc', 1)],
        ['a2', asFullKey('a1', false, 0)],
      ],
      ['b4', asFullKey('b2', false, 0)],
      undefined,
      'b2',
    ),
    11,
  );
  const v2 = await execute(
    graph,
    scrollTopHorizontal(v1, HDirection.Right),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [
        ['a1', asUserKey('abc', 1)],
        ['a1', asUserKey('abc', 2)],
        ['a1', asUserKey('abc', 3)],
      ],
      [
        undefined,
        ['c2', asUserChildKey('abc', 2)],
        ['a2', asFullKey('a1', false, 0)],
      ],
      undefined,
      undefined,
      'c2',
    ),
    11,
  );
  const v3 = await execute(
    graph,
    scrollTopHorizontal(v2, HDirection.Right),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [
        ['a1', asUserKey('abc', 2)],
        ['a1', asUserKey('abc', 3)],
        ['a2', asUserKey('abc', 4)],
      ],
      [
        undefined,
        ['d2', asUserChildKey('abc', 3)],
        ['a2', asFullKey('a1', false, 0)],
      ],
      undefined,
      undefined,
      'd2',
    ),
    11,
  );
  const v4 = await execute(
    graph,
    scrollTopHorizontal(v3, HDirection.Right),
    buildFullView(
      ['a1', asFullKey('a2', true, 0)],
      [
        ['a1', asUserKey('abc', 3)],
        ['a2', asUserKey('abc', 4)],
        ['a3', asUserKey('abc', 5)],
      ],
      [undefined, ['a3', asUserChildKey('abc', 4)], undefined],
      ['a4', asFullKey('a3', false, 0)],
      undefined,
      'a3',
    ),
    11,
  );

  await execute(graph, scrollTopHorizontal(v4, HDirection.Left), v3, 11);
  await execute(graph, scrollTopHorizontal(v3, HDirection.Left), v2, 11);

  const v5 = await execute(
    graph,
    scrollBottomHorizontal(v2, HDirection.Right),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], undefined],
      [
        ['c2', asUserChildKey('abc', 2)],
        ['a2', asFullKey('a1', false, 0)],
        ['b2', asFullKey('a1', false, 1)],
      ],
      ['a3', asFullKey('a2', false, 0)],
      'a1',
      'c2',
    ),
    6,
  );
  await execute(
    graph,
    scrollBottomHorizontal(v5, HDirection.Left),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], undefined],
      [
        undefined,
        ['c2', asUserChildKey('abc', 2)],
        ['a2', asFullKey('a1', false, 0)],
      ],
      undefined,
      'a1',
      'c2',
    ),
    6,
  );
  const v6 = await execute(
    graph,
    scrollBottomHorizontal(v5, HDirection.Right),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], ['b4', asFullKey('b2', true, 1)]],
      [
        ['a2', asFullKey('a1', false, 0)],
        ['b2', asFullKey('a1', false, 1)],
        ['d2', asFullKey('a1', false, 3)],
      ],
      ['b4', asFullKey('b2', false, 0)],
      'a1',
      'c2',
    ),
    6,
  );
  await execute(
    graph,
    scrollBottomHorizontal(v6, HDirection.Left),
    buildFullView(
      ['a5', asFullKey('a1', true, 0)],
      [undefined, ['a1', asDirectKey('a1')], undefined],
      [
        ['c2', asDirectKey('c2')],
        ['a2', asFullKey('a1', false, 0)],
        ['b2', asFullKey('a1', false, 1)],
      ],
      ['a3', asFullKey('a2', false, 0)],
      'a1',
      'c2',
    ),
    6,
  );

  const { view: invalidView, change: invalidChange } = await progressView(
    graph,
    initUserView('foo' as UserId),
    undefined,
  );
  assertTrue(invalidChange, 'one change');
  assertTrue(
    equalView(invalidView, {
      centerTop: {
        content: '[deleted]',
        fullKey: asUserKey('foo', 0),
        invalid: true,
      },
    }),
    'should be invalid',
  );
  const { view: nextInvalidView, change: nextInvalidChange } =
    await progressView(graph, invalidView, undefined);
  assertTrue(!nextInvalidChange, 'no more changes');
  assertTrue(equalView(invalidView, nextInvalidView), 'should be no change');
});
