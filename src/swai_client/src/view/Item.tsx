import React, { PureComponent, ReactNode } from 'react';
import styled from 'styled-components';
import { Cell } from '../graph/GraphView';
import { safeStringify } from '../misc/util';
import Content from './Content';

export const ItemDiv = styled.div`
  display: inline-block;
  white-space: nowrap;
  vertical-align: top;
  margin: 0;
  padding: 0;
  width: var(--main-size);
  height: var(--main-size);
  scroll-snap-align: center;
`;

export const ItemContent = styled.div<ItemContentProps>`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  width: var(--item-size);
  height: var(--item-size);
  margin: 0;
  border-radius: var(--item-radius);
  padding: var(--item-padding);
  white-space: normal;
  overflow: hidden;
  background-color: var(--item-background);
  box-shadow: ${(props) =>
    props.isLocked
      ? 'inset 0 0 32px 0 var(--item-lock)'
      : 'inset 0 0 32px 0 var(--item-background-dim)'};
`;

type ItemContentProps = {
  isLocked: boolean;
};

function getContent(cell: Readonly<Cell> | undefined): ReactNode {
  if (cell === undefined) {
    return '[loading]';
  }
  if (cell.content === undefined) {
    return `[loading...${safeStringify(cell.fullKey)}]`;
  }
  return <Content>{cell.content}</Content>;
}

type ItemProps = {
  refObj?: React.RefObject<HTMLDivElement>;
  cell: Readonly<Cell> | undefined;
  isLocked: boolean;
  children?: ReactNode;
};

export default class Item extends PureComponent<ItemProps> {
  render(): ReactNode {
    const { refObj, cell, isLocked, children } = this.props;
    return (
      <ItemDiv ref={refObj}>
        {children}
        <ItemContent isLocked={isLocked}>{getContent(cell)}</ItemContent>
      </ItemDiv>
    );
  }
} // Item
