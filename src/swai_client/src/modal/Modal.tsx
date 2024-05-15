import { connect, ConnectedProps } from 'react-redux';
import React, { PureComponent, ReactNode } from 'react';
import styled from 'styled-components';
import { RootState } from '../store';
import { ActiveModal, setModal } from './ModalStateSlice';

const ModalFull = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
`;

const ModalOutside = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  opacity: 0.8;
  background-color: var(--main-background);
  pointer-events: auto;
`;

const ModalMain = styled.div`
  position: relative;
  color: var(--main-text);
  background-color: var(--item-background);
  border-radius: var(--item-radius-sm);
  padding: 0 var(--item-padding);
  pointer-events: auto;
  box-shadow: 0 0 16px var(--item-radius-sm) var(--item-shadow);
`;

const ModalPad = styled.div`
  display: flex;
  flex-direction: column;
  justify-content: center;
  width: 100%;
  height: var(--item-radius);
  text-align: center;
  vertical-align: middle;
  padding: var(--item-padding) 0;
`;

const ModalExit = styled.button`
  position: absolute;
  top: 0;
  right: 0;
  user-select: none;
  appearance: none;
  text-align: center;
  vertical-align: middle;
  pointer-events: auto;
  cursor: pointer;
  border: 0;
  border-radius: var(--item-radius);
  padding: 0;
  margin: var(--item-padding);
  cursor: pointer;
  background-color: unset;
  color: var(--button-text);

  &:hover {
    color: var(--button-text-hover);
  }
  &:active {
    color: var(--button-text-active);
  }
`;

const Header = styled.span`
  font-size: 1.5em;
`;

const Footer = styled.span`
  font-size: 0.75em;
`;

interface ModalProps extends ConnectUser {
  modalTrigger: Readonly<ActiveModal>;
  header?: string;
  footer?: string;
  children: ReactNode;
  onOpen?: () => void;
  onClose?: () => void;
}

type ModalState = {
  isShowing: boolean;
};

class Modal extends PureComponent<ModalProps, ModalState> {
  constructor(props: ModalProps) {
    super(props);
    this.state = { isShowing: false };
  }

  componentDidMount(): void {
    this.componentDidUpdate();
  }

  componentDidUpdate(): void {
    const { modalTrigger, curModal, onOpen, onClose } = this.props;
    const { isShowing } = this.state;
    const nextIsShowing = modalTrigger === curModal;
    if (nextIsShowing !== isShowing) {
      if (nextIsShowing) {
        onOpen !== undefined && onOpen();
      } else {
        onClose !== undefined && onClose();
      }
      this.setState({
        isShowing: nextIsShowing,
      });
    }
  }

  private closeModal(): void {
    const { dispatch } = this.props;
    dispatch(setModal({ activeModal: ActiveModal.None }));
  }

  handleModalOutside = (event: React.MouseEvent<HTMLElement>): void => {
    this.closeModal();
    event.preventDefault();
  };

  render(): ReactNode {
    const { isShowing } = this.state;
    if (!isShowing) {
      return null;
    }
    const { header, footer, children } = this.props;
    return (
      <React.Fragment>
        <ModalOutside onClick={this.handleModalOutside} />
        <ModalFull>
          <ModalMain>
            <ModalPad>
              {header !== undefined ? <Header>{header}</Header> : null}
              <ModalExit onClick={this.handleModalOutside}>✖</ModalExit>
            </ModalPad>
            {children}
            <ModalPad>
              {footer !== undefined ? <Footer>{footer}</Footer> : null}
            </ModalPad>
          </ModalMain>
        </ModalFull>
      </React.Fragment>
    );
  }
} // Modal

const connector = connect((state: RootState) => ({
  curModal: state.modalState.activeModal,
}));

export default connector(Modal);

type ConnectUser = ConnectedProps<typeof connector>;
