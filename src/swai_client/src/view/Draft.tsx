import { connect, ConnectedProps } from 'react-redux';
import React, { PureComponent, ReactNode } from 'react';
import styled from 'styled-components';
import { RootState } from '../store';
import { Cell } from '../graph/GraphView';
import Item, { ItemContent, ItemDiv } from './Item';
import { HOverlay, NavButton, WMOverlay } from './buttons';
import { MHash, ValidLink } from '../api/types';
import UserActions from '../users/UserActions';
import { errHnd } from '../misc/util';
import { INVALID_FULL_KEY } from '../graph/keys';

const DraftInput = styled.textarea`
  appearance: none;
  margin: auto 0;
  width: var(--md-size-w);
  height: var(--md-size-h);
  resize: none;
`;

const DraftSubmit = styled.input`
  appearance: none;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  vertical-align: middle;
  border-radius: var(--button-radius);
  width: var(--button-size);
  height: var(--button-size);
  cursor: pointer;
  padding: 0;
  font-size: 2em;
  border: 0;
  opacity: 0.8;
  color: var(--button-text-dim);
  pointer-events: auto;
  border-style: none;
  background-color: var(--button-background);

  &:hover {
    background-color: var(--button-hover);
  }
  &:active {
    background-color: var(--button-active);
  }
`;

const CloseButton = styled(NavButton)`
  font-size: 1.5em;
`;

const PreviewButton = styled(NavButton)``;

export type DraftMode = {
  parent: Readonly<Cell>;
};

interface DraftProps extends ConnectDraft {
  userActions: UserActions;
  draft: Readonly<DraftMode> | undefined;
  onClose: (link: Readonly<ValidLink> | undefined) => void;
}

type DraftState = {
  draftValue: string;
  awaitFocus: boolean;
  lastParent: Readonly<MHash> | undefined;
  isOpen: boolean;
  isPreview: boolean;
  preview: Readonly<Cell> | undefined;
};

class Draft extends PureComponent<DraftProps, DraftState> {
  private readonly inputRef: React.RefObject<HTMLTextAreaElement>;

  constructor(props: DraftProps) {
    super(props);
    this.state = {
      draftValue: '',
      awaitFocus: false,
      lastParent: undefined,
      isOpen: false,
      isPreview: false,
      preview: undefined,
    };
    this.inputRef = React.createRef();
  }

  componentDidMount(): void {
    this.componentDidUpdate();
  }

  componentDidUpdate(): void {
    const { draft } = this.props;
    const { awaitFocus, lastParent, isOpen } = this.state;
    const newIsOpen = draft !== undefined;
    if (newIsOpen !== isOpen) {
      this.setState({ isOpen: newIsOpen, isPreview: false });
    }
    if (newIsOpen) {
      const { parent } = draft;
      if (parent.mhash !== lastParent) {
        this.setState({
          lastParent: parent.mhash,
          draftValue: '',
          preview: { fullKey: INVALID_FULL_KEY, content: '' },
          awaitFocus: true,
        });
      }
    }
    if ((newIsOpen || awaitFocus) && this.inputRef.current) {
      this.inputRef.current.focus();
      this.setState({ awaitFocus: false });
    }
  }

  handleChange = (event: React.FormEvent<HTMLTextAreaElement>): void => {
    const draftValue = event.currentTarget.value;
    this.setState({
      draftValue,
      preview: { fullKey: INVALID_FULL_KEY, content: draftValue.trim() },
    });
  };

  private closeDraft(link: Readonly<ValidLink> | undefined) {
    const { onClose } = this.props;
    onClose(link);
  }

  handleSubmit = (event: React.FormEvent<HTMLFormElement>): void => {
    const { userActions, user, draft } = this.props;
    const { draftValue } = this.state;
    if (
      draft !== undefined &&
      draft.parent.mhash !== undefined &&
      draftValue &&
      user !== undefined
    ) {
      userActions
        .writeMessage(user.token, draft.parent.mhash, draftValue)
        .then(
          (link) => {
            this.closeDraft(link);
          },
          (e) => {
            errHnd(e);
          },
        );
    }
    event.preventDefault();
  };

  handlePreview = (event: React.FormEvent<HTMLElement>): void => {
    const { isPreview } = this.state;
    this.setState({ isPreview: !isPreview });
    event.preventDefault();
  };

  handleClose = (event: React.FormEvent<HTMLElement>): void => {
    this.closeDraft(undefined);
    event.preventDefault();
  };

  render(): ReactNode {
    const { draft } = this.props;
    const { isOpen, isPreview, preview } = this.state;
    if (!isOpen || draft === undefined) {
      return null;
    }
    const { draftValue } = this.state;
    const parent = draft.parent;
    return (
      <form onSubmit={this.handleSubmit}>
        <WMOverlay
          isLeft={true}
          isVisible={true}>
          <PreviewButton
            isChecked={isPreview}
            onClick={this.handlePreview}>
            🔍
          </PreviewButton>
        </WMOverlay>
        <WMOverlay
          isLeft={false}
          isVisible={true}>
          <DraftSubmit
            type="submit"
            value="✉"
          />
        </WMOverlay>
        <Item
          cell={isPreview && preview !== undefined ? preview : parent}
          isLocked={false}
        />
        <ItemDiv>
          <ItemContent isLocked={false}>
            <DraftInput
              value={draftValue}
              ref={this.inputRef}
              onChange={this.handleChange}
            />
          </ItemContent>
        </ItemDiv>
        <HOverlay
          isTop={true}
          isVisible={true}
          forceRight={true}>
          <CloseButton onClick={this.handleClose}>✖</CloseButton>
        </HOverlay>
      </form>
    );
  }
} // Draft

const connector = connect((state: RootState) => ({
  user: state.userState.currentUser,
}));

export default connector(Draft);

type ConnectDraft = ConnectedProps<typeof connector>;
