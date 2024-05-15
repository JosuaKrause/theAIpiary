import { connect, ConnectedProps } from 'react-redux';
import React, { PureComponent, ReactNode } from 'react';
import styled from 'styled-components';
import { RootState } from '../store';
import {
  Cell,
  Direction,
  horizontal,
  NavigationCB,
  progressView,
  replaceLink,
  scrollBottomHorizontal,
  scrollTopHorizontal,
  scrollVertical,
  TopLinkKey,
  vertical,
} from '../graph/GraphView';
import CommentGraph, { toActiveUser } from '../graph/CommentGraph';
import { errHnd, SafeMap } from '../misc/util';
import { initLink, initUser, refreshLinks, setView } from './ViewStateSlice';
import UserActions from '../users/UserActions';
import { FullKeyType } from '../graph/keys';
import { ValidLink, VoteType } from '../api/types';
import TopLink, {
  UserCallback,
  VoteCallback,
  VoteCallbackKey,
} from './TopLink';
import Item from './Item';
import Draft, { DraftMode } from './Draft';
import {
  HNavButton,
  HOverlay,
  VNavButton,
  WMOverlay,
  WriteMessageButton,
} from './buttons';

const Outer = styled.div`
  position: relative;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
`;

const Temp = styled.div<TempProps>`
  display: ${(props) => (props.isVisible ? 'block' : 'none')};
  position: relative;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  overflow: hidden;
`;

const VBand = styled.div<NoScrollProps>`
  margin: 0;
  padding: 0;
  display: block;
  width: 100%;
  height: 100%;
  vertical-align: top;
  background-color: var(--main-background);
  overflow-x: hidden;
  overflow-y: ${(props) => (props.noScroll ? 'hidden' : 'scroll')};

  &::-webkit-scrollbar {
    display: none;
  }

  -ms-overflow-style: none;
  scrollbar-width: none;
  scroll-snap-type: y mandatory;
`;

const HBand = styled.div<NoScrollProps>`
  margin: 0;
  padding: 0;
  display: inline-block;
  width: 100%;
  height: var(--main-size);
  white-space: nowrap;
  vertical-align: top;
  overflow-x: ${(props) => (props.noScroll ? 'hidden' : 'scroll')};
  overflow-y: hidden;

  &::-webkit-scrollbar {
    display: none;
  }

  -ms-overflow-style: none;
  scrollbar-width: none;
  scroll-snap-type: x mandatory;
  scroll-snap-align: start;
`;

type NoScrollProps = {
  noScroll: boolean;
};

type TempProps = {
  isVisible: boolean;
};

enum ResetView {
  StopScroll = 'StopScroll',
  ResetBottom = 'ResetBottom',
  ResetTop = 'ResetTop',
  Done = 'Done',
}

type Refs = {
  top: React.RefObject<HTMLDivElement>;
  topLeft: React.RefObject<HTMLDivElement>;
  centerTop: React.RefObject<HTMLDivElement>;
  topRight: React.RefObject<HTMLDivElement>;
  bottomLeft: React.RefObject<HTMLDivElement>;
  centerBottom: React.RefObject<HTMLDivElement>;
  bottomRight: React.RefObject<HTMLDivElement>;
  bottom: React.RefObject<HTMLDivElement>;
};

type Obs = {
  top: IntersectionObserver | undefined;
  topLeft: IntersectionObserver | undefined;
  topRight: IntersectionObserver | undefined;
  bottomLeft: IntersectionObserver | undefined;
  bottomRight: IntersectionObserver | undefined;
  bottom: IntersectionObserver | undefined;
};

type ObsKey = keyof Obs;

const navigationCBs: { [Property in ObsKey]: [NavigationCB, Direction] } = {
  top: [vertical(scrollVertical), Direction.UpRight],
  topLeft: [horizontal(scrollTopHorizontal), Direction.DownLeft],
  topRight: [horizontal(scrollTopHorizontal), Direction.UpRight],
  bottomLeft: [horizontal(scrollBottomHorizontal), Direction.DownLeft],
  bottomRight: [horizontal(scrollBottomHorizontal), Direction.UpRight],
  bottom: [vertical(scrollVertical), Direction.DownLeft],
};

const scrollBlocks: { [Property in ObsKey]: ScrollLogicalPosition } = {
  top: 'start',
  topLeft: 'start',
  topRight: 'start',
  bottomLeft: 'end',
  bottomRight: 'end',
  bottom: 'end',
};

interface ViewProps extends ConnectView {
  graph: CommentGraph;
  userActions: UserActions;
}

type EmptyViewProps = {
  view: undefined;
  user: undefined;
};

type ViewState = {
  resetView: ResetView;
  redraw: boolean;
  tempContent: [Readonly<Cell> | undefined, Readonly<Cell> | undefined];
  pending: [NavigationCB, Direction] | undefined;
  draft: Readonly<DraftMode> | undefined;
};

class View extends PureComponent<ViewProps, ViewState> {
  private readonly rootRef: React.RefObject<HTMLDivElement>;
  private readonly curRefs: Refs;
  private readonly curObs: Obs;
  private readonly voteCallbacks: SafeMap<VoteCallbackKey, VoteCallback>;
  private readonly userCallbacks: SafeMap<TopLinkKey, UserCallback>;

  constructor(props: Readonly<ViewProps>) {
    super(props);
    this.state = {
      resetView: ResetView.ResetBottom,
      redraw: false,
      tempContent: [undefined, undefined],
      pending: undefined,
      draft: undefined,
    };
    this.rootRef = React.createRef();
    this.curRefs = {
      top: React.createRef(),
      topLeft: React.createRef(),
      centerTop: React.createRef(),
      topRight: React.createRef(),
      bottomLeft: React.createRef(),
      centerBottom: React.createRef(),
      bottomRight: React.createRef(),
      bottom: React.createRef(),
    };
    this.curObs = {
      top: undefined,
      topLeft: undefined,
      topRight: undefined,
      bottomLeft: undefined,
      bottomRight: undefined,
      bottom: undefined,
    };
    this.voteCallbacks = new SafeMap();
    this.userCallbacks = new SafeMap();
  }

  componentDidMount(): void {
    this.componentDidUpdate({ view: undefined, user: undefined }, undefined);
  }

  componentDidUpdate(
    prevProps: Readonly<ViewProps> | EmptyViewProps,
    _prevState: Readonly<ViewState> | undefined,
  ): void {
    const { graph, view, changes, user, dispatch } = this.props;
    const { resetView, redraw, pending } = this.state;
    const activeUser = toActiveUser(user);
    if (user !== prevProps.user) {
      dispatch(refreshLinks({ changes }));
    }
    if (view !== prevProps.view || pending !== undefined) {
      progressView(graph, view, activeUser).then(
        ({ view: newView, change }) => {
          if (change) {
            dispatch(setView({ view: newView, changes, progress: true }));
            return;
          }
          if (pending !== undefined) {
            const [navigator, direction] = pending;
            const nextView = navigator(newView, direction);
            if (nextView !== undefined) {
              dispatch(setView({ view: nextView, changes, progress: false }));
            }
            this.setState({ pending: undefined });
          }
        },
        (e) => {
          errHnd(e);
        },
      );
    }
    if (resetView !== ResetView.Done) {
      if (resetView === ResetView.StopScroll) {
        if (pending === undefined) {
          setTimeout(() => {
            this.setState({ resetView: ResetView.ResetBottom });
          }, 100);
        }
      } else if (
        resetView === ResetView.ResetBottom &&
        this.curRefs.centerBottom.current !== null
      ) {
        this.curRefs.centerBottom.current.scrollIntoView({
          behavior: 'auto',
          block: 'end',
          inline: 'nearest',
        });
        this.setState({ resetView: ResetView.ResetTop });
      } else if (this.curRefs.centerTop.current !== null) {
        this.curRefs.centerTop.current.scrollIntoView({
          behavior: 'auto',
          block: 'start',
          inline: 'nearest',
        });
        this.setState({
          resetView: ResetView.Done,
          tempContent: [undefined, undefined],
        });
      }
    }

    const ensureObserver = (key: ObsKey): boolean => {
      if (this.curObs[key] !== undefined) {
        return true;
      }
      const current = this.curRefs[key].current;
      if (current === null) {
        return false;
      }
      const root = this.rootRef.current;
      if (root === null) {
        return false;
      }
      const observer = new IntersectionObserver(
        (entries) => {
          const { pending, resetView } = this.state;
          let done = pending !== undefined || resetView !== ResetView.Done;
          entries.forEach((entry) => {
            if (!entry.isIntersecting) {
              return;
            }
            if (done) {
              return;
            }
            this.navigate(key, ...navigationCBs[key]);
            done = true;
          });
        },
        {
          root,
          rootMargin: '0px',
          threshold: 0.9,
        },
      );
      observer.observe(current);
      this.curObs[key] = observer;
      return true;
    };
    const obsReady = Object.keys(this.curObs).map((key) => {
      return ensureObserver(key as ObsKey);
    });
    if (!obsReady.every((res) => res)) {
      console.warn('delayed intersection observers!');
      this.setState({ redraw: !redraw });
    }
  }

  private getTempConfig(
    key: ObsKey,
  ): [Readonly<Cell> | undefined, Readonly<Cell> | undefined] {
    const { view } = this.props;
    if (key === 'top') {
      return [view.top, view.centerTop];
    }
    if (key == 'topLeft') {
      return [view.topLeft, view.centerBottom];
    }
    if (key == 'topRight') {
      return [view.topRight, view.centerBottom];
    }
    if (key == 'bottomLeft') {
      return [view.centerTop, view.bottomLeft];
    }
    if (key == 'bottomRight') {
      return [view.centerTop, view.bottomRight];
    }
    if (key == 'bottom') {
      return [view.centerBottom, view.bottom];
    }
    return [view.centerTop, view.centerBottom];
  }

  private isNoScroll(): boolean {
    const { resetView } = this.state;
    return resetView === ResetView.StopScroll;
  }

  private navigate(
    key: ObsKey,
    navigator: NavigationCB,
    direction: Direction,
  ): void {
    const { dispatch, view, changes } = this.props;
    const newView = navigator(view, direction);
    if (newView !== undefined) {
      dispatch(setView({ view: newView, changes, progress: false }));
    } else {
      this.setState({ pending: [navigator, direction] });
    }
    this.setState({
      resetView: ResetView.StopScroll,
      tempContent: this.getTempConfig(key),
    });
  }

  private getVoteHandle(key: Readonly<VoteCallbackKey>): VoteCallback {
    let res = this.voteCallbacks.get(key);
    if (res === undefined) {
      res = (event) => {
        const { position, voteType, isAdd } = key;
        const { view, user, changes, userActions, dispatch } = this.props;
        const cell = view[position];
        const link =
          cell !== undefined && !cell.invalid ? cell.topLink : undefined;
        if (user !== undefined && link !== undefined && !link.invalid) {
          userActions
            .vote(user.token, link.parent, link.child, [voteType], isAdd)
            .then(
              (newLink) => {
                dispatch(
                  setView({
                    view: replaceLink(view, position, newLink),
                    changes,
                    progress: false,
                  }),
                );
              },
              (e) => {
                errHnd(e);
              },
            );
        }
        event.preventDefault();
      };
      this.voteCallbacks.set(key, res);
    }
    return res;
  }

  maybeVoteHandle = (
    position: TopLinkKey | undefined,
    voteType: VoteType,
    isAdd: boolean,
    noScroll: boolean,
  ): VoteCallback | undefined => {
    return !noScroll && position !== undefined
      ? this.getVoteHandle({
          position,
          voteType,
          isAdd,
        })
      : undefined;
  };

  private getUserHandle(key: Readonly<TopLinkKey>): UserCallback {
    let res = this.userCallbacks.get(key);
    if (res === undefined) {
      res = (event) => {
        const { view, changes, dispatch } = this.props;
        const cell = view[key];
        const link =
          cell !== undefined && !cell.invalid ? cell.topLink : undefined;
        if (link !== undefined && !link.invalid && link.userId !== undefined) {
          dispatch(initUser({ userId: link.userId, changes }));
        }
        event.preventDefault();
      };
      this.userCallbacks.set(key, res);
    }
    return res;
  }

  maybeUserHandle = (
    key: Readonly<TopLinkKey> | undefined,
    noScroll: boolean,
  ): UserCallback | undefined => {
    return !noScroll && key !== undefined
      ? this.getUserHandle(key)
      : undefined;
  };

  handleWriteMessage = (event: React.MouseEvent<HTMLElement>): void => {
    const { view, user } = this.props;
    if (user !== undefined) {
      this.setState({
        draft: {
          parent: view.centerTop,
        },
      });
    }
    event.preventDefault();
  };

  onCloseDraft = (link: Readonly<ValidLink> | undefined): void => {
    if (link !== undefined) {
      const { changes, dispatch } = this.props;
      dispatch(initLink({ link, changes }));
    }
    this.setState({ draft: undefined });
  };

  private handleButtons(
    event: React.MouseEvent<HTMLElement>,
    key: ObsKey,
  ): void {
    const current = this.curRefs[key].current;
    if (current !== null && !this.isNoScroll()) {
      current.scrollIntoView({
        behavior: 'smooth',
        block: scrollBlocks[key],
        inline: 'nearest',
      });
    }
    event.preventDefault();
  }

  handleUp = (event: React.MouseEvent<HTMLElement>): void => {
    this.handleButtons(event, 'top');
  };

  handleDown = (event: React.MouseEvent<HTMLElement>): void => {
    this.handleButtons(event, 'bottom');
  };

  handleTopRight = (event: React.MouseEvent<HTMLElement>): void => {
    this.handleButtons(event, 'topRight');
  };

  handleTopLeft = (event: React.MouseEvent<HTMLElement>): void => {
    this.handleButtons(event, 'topLeft');
  };

  handleBottomRight = (event: React.MouseEvent<HTMLElement>): void => {
    this.handleButtons(event, 'bottomRight');
  };

  handleBottomLeft = (event: React.MouseEvent<HTMLElement>): void => {
    this.handleButtons(event, 'bottomLeft');
  };

  render(): ReactNode {
    const { userActions, user, view } = this.props;
    const { tempContent, draft } = this.state;
    const noScroll = this.isNoScroll();
    const isDraftMode = draft !== undefined;

    const isLocked =
      view.centerTop.fullKey.fullKeyType === FullKeyType.topic ||
      view.centerTop.fullKey.fullKeyType === FullKeyType.user;
    const getUserCB = this.maybeUserHandle;
    const getVoteCB = this.maybeVoteHandle;
    return (
      <Outer ref={this.rootRef}>
        <Temp isVisible={isDraftMode}>
          <Draft
            userActions={userActions}
            draft={draft}
            onClose={this.onCloseDraft}
          />
        </Temp>
        <Temp isVisible={noScroll && !isDraftMode}>
          <Item
            cell={tempContent[0]}
            isLocked={isLocked}>
            <TopLink
              cell={tempContent[0]}
              position={undefined}
              noScroll={noScroll}
              getUserCB={getUserCB}
              getVoteCB={getVoteCB}
            />
          </Item>
          <Item
            cell={tempContent[1]}
            isLocked={isLocked}>
            <TopLink
              cell={tempContent[1]}
              position={undefined}
              noScroll={noScroll}
              getUserCB={getUserCB}
              getVoteCB={getVoteCB}
            />
          </Item>
        </Temp>
        <VBand noScroll={noScroll}>
          <HBand noScroll={noScroll}>
            <Item
              refObj={this.curRefs.top}
              cell={view.top}
              isLocked={false}
            />
          </HBand>
          <HBand noScroll={noScroll}>
            <Item
              refObj={this.curRefs.topLeft}
              cell={view.topLeft}
              isLocked={isLocked}
            />
            <Item
              refObj={this.curRefs.centerTop}
              cell={view.centerTop}
              isLocked={isLocked}>
              <TopLink
                cell={view.centerTop}
                position="centerTop"
                noScroll={noScroll}
                getUserCB={getUserCB}
                getVoteCB={getVoteCB}
              />
            </Item>
            <Item
              refObj={this.curRefs.topRight}
              cell={view.topRight}
              isLocked={isLocked}
            />
          </HBand>
          <HBand noScroll={noScroll}>
            <Item
              refObj={this.curRefs.bottomLeft}
              cell={view.bottomLeft}
              isLocked={isLocked}>
              <TopLink
                cell={view.bottomLeft}
                position="bottomLeft"
                noScroll={noScroll}
                getUserCB={getUserCB}
                getVoteCB={getVoteCB}></TopLink>
            </Item>
            <Item
              refObj={this.curRefs.centerBottom}
              cell={view.centerBottom}
              isLocked={isLocked}>
              <TopLink
                cell={view.centerBottom}
                position="centerBottom"
                noScroll={noScroll}
                getUserCB={getUserCB}
                getVoteCB={getVoteCB}></TopLink>
            </Item>
            <Item
              refObj={this.curRefs.bottomRight}
              cell={view.bottomRight}
              isLocked={isLocked}>
              <TopLink
                cell={view.bottomRight}
                position="bottomRight"
                noScroll={noScroll}
                getUserCB={getUserCB}
                getVoteCB={getVoteCB}></TopLink>
            </Item>
          </HBand>
          <HBand noScroll={noScroll}>
            <Item
              refObj={this.curRefs.bottom}
              cell={view.bottom}
              isLocked={false}>
              <TopLink
                cell={view.bottom}
                position="bottom"
                noScroll={noScroll}
                getUserCB={getUserCB}
                getVoteCB={getVoteCB}></TopLink>
            </Item>
          </HBand>
        </VBand>
        <HOverlay
          isTop={true}
          isVisible={!isDraftMode}>
          <HNavButton onClick={this.handleTopLeft}>◀</HNavButton>
          <HNavButton onClick={this.handleTopRight}>▶</HNavButton>
        </HOverlay>
        <HOverlay
          isTop={false}
          isVisible={!isDraftMode}>
          <HNavButton onClick={this.handleBottomLeft}>◀</HNavButton>
          <HNavButton onClick={this.handleBottomRight}>▶</HNavButton>
        </HOverlay>
        <VNavButton
          isTop={true}
          isVisible={!isDraftMode}
          onClick={this.handleUp}>
          ▲
        </VNavButton>
        <VNavButton
          isTop={false}
          isVisible={!isDraftMode}
          onClick={this.handleDown}>
          ▼
        </VNavButton>
        <WMOverlay
          isLeft={false}
          isVisible={user !== undefined && !isDraftMode}>
          <WriteMessageButton onClick={this.handleWriteMessage}>
            ✎
          </WriteMessageButton>
        </WMOverlay>
      </Outer>
    );
  }
} // View

const connector = connect((state: RootState) => ({
  user: state.userState.currentUser,
  view: state.viewState.currentView,
  changes: state.viewState.currentChanges,
}));

export default connector(View);

type ConnectView = ConnectedProps<typeof connector>;
