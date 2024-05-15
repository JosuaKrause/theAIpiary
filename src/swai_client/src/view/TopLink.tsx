import React, { PureComponent } from 'react';
import styled from 'styled-components';
import { Cell, TopLinkKey } from '../graph/GraphView';
import { RichVote, VoteType, VOTE_TYPES } from '../api/types';
import { toReadableNumber } from '../misc/util';

const DEBUG_LINKS = true;

const VOTE_SYMBOL = {
  up: '👍',
  down: '👎',
  honor: '⭐',
};

const ItemMid = styled.div`
  display: flex;
  width: 100%;
  height: 0;
  position: relative;
  top: var(--mid-top);
  left: 0;
  align-items: center;
  justify-content: center;
  text-align: center;
  opacity: 0.8;
  flex-direction: column;
`;

const ItemMidVotes = styled.div`
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
`;

const ButtonDiv = styled.div<ButtonDivProps>`
  display: inline-block;
  text-align: center;
  vertical-align: middle;
  pointer-events: auto;
  cursor: pointer;
  border: 0;
  ${(props) =>
    props.isChecked ? 'background-color: var(--button-background-lit);' : ''}

  &:hover {
    background-color: ${(props) =>
      props.isChecked ? 'var(--button-active)' : 'var(--button-hover)'};
  }
  &:active {
    background-color: ${(props) =>
      props.isChecked ? 'var(--button-hover)' : 'var(--button-active)'};
  }
`;

const ItemMidName = styled(ButtonDiv)`
  font-size: 0.6em;
  align-items: center;
  justify-content: center;
  border-radius: var(--mid-user-radius);
  margin-top: var(--mid-user-top);
  padding: var(--mid-user-padding);
`;

const ItemMidContent = styled(ButtonDiv)`
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: row;
  height: var(--vote-size);
  border-radius: var(--vote-radius);
  padding: var(--vote-padding);
`;

type ButtonDivProps = {
  isChecked: boolean;
};

export type VoteCallbackKey = {
  position: TopLinkKey;
  voteType: VoteType;
  isAdd: boolean;
};

export type UserCallback = (event: React.MouseEvent<HTMLElement>) => void;
export type VoteCallback = (event: React.MouseEvent<HTMLElement>) => void;

type TopLinkProps = {
  cell: Readonly<Cell> | undefined;
  position: Readonly<TopLinkKey> | undefined;
  noScroll: boolean;
  getUserCB: (
    key: Readonly<TopLinkKey> | undefined,
    noScroll: boolean,
  ) => UserCallback | undefined;
  getVoteCB: (
    position: Readonly<TopLinkKey> | undefined,
    voteType: Readonly<VoteType>,
    isAdd: boolean,
    noScroll: boolean,
  ) => VoteCallback | undefined;
};

export default class TopLink extends PureComponent<TopLinkProps> {
  render() {
    const { cell, getUserCB, position, noScroll, getVoteCB } = this.props;
    if (cell === undefined) {
      return null;
    }
    if (cell.topLink === undefined) {
      return null;
    }
    const link = cell.topLink;
    if (link.invalid) {
      return null;
    }
    const userCB = getUserCB(position, noScroll);
    return (
      <ItemMid>
        <ItemMidVotes>
          {VOTE_TYPES.map((voteType: VoteType): RichVote => {
            const res = link.votes[voteType];
            if (res === undefined) {
              return { voteType, count: 0, userVoted: false };
            }
            const { count, userVoted } = res;
            return { voteType, count, userVoted };
          }).map(({ voteType, count, userVoted }) => {
            const voteCB = getVoteCB(position, voteType, !userVoted, noScroll);
            return (
              <ItemMidContent
                key={voteType}
                onClick={voteCB}
                isChecked={userVoted}>
                {toReadableNumber(count)} {VOTE_SYMBOL[voteType]}
              </ItemMidContent>
            );
          })}
        </ItemMidVotes>
        <ItemMidName
          onClick={userCB}
          isChecked={false}>
          {link.username}
          {DEBUG_LINKS ? `${link.username ? ' ' : ''}(${link.meta})` : null}
        </ItemMidName>
      </ItemMid>
    );
  }
} // TopLink
