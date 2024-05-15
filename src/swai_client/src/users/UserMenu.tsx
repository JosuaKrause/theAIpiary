import { connect, ConnectedProps } from 'react-redux';
import React, { PureComponent, ReactNode } from 'react';
import styled from 'styled-components';
import UserActions from './UserActions';
import { RootState } from '../store';
import { setUser } from './UserStateSlice';
import { errHnd } from '../misc/util';
import { Username } from '../api/types';
import Modal from '../modal/Modal';
import { ActiveModal, setModal } from '../modal/ModalStateSlice';
import { initTopic, initUser } from '../view/ViewStateSlice';

const Menu = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  text-align: center;
  vertical-align: middle;
  border: 0;
  color: var(--button-text);
  border-radius: var(--button-radius);
  background-color: var(--button-background-lit);
  width: max-content;
`;

const MenuItem = styled.div`
  display: flex;
  flex-direction: row;
  justify-content: end;
  text-align: right;
  vertical-align: middle;
  height: var(--button-size);
`;

const MenuButton = styled.button`
  font-size: 1.5em;
  flex-shrink: 0;
  flex-grow: 0;
  appearance: none;
  text-align: center;
  vertical-align: middle;
  pointer-events: auto;
  cursor: pointer;
  border: 0;
  opacity: 0.8;
  color: var(--button-text);
  border-radius: var(--button-radius);
  width: var(--button-size);
  height: var(--button-size);
  background-color: var(--button-background);
  border-style: groove;

  &:hover {
    background-color: var(--button-hover);
  }
  &:active {
    background-color: var(--button-active);
    border-style: inset;
  }
`;

const Pad = styled.div`
  flex-shrink: 0;
  flex-grow: 0;
  width: var(--button-size);
  background-color: unset;
`;

const MenuItemButton = styled.button`
  flex-shrink: 0;
  flex-grow: 0;
  appearance: none;
  padding: 0 1em;
  text-align: end;
  vertical-align: middle;
  pointer-events: auto;
  cursor: pointer;
  border: 0;
  opacity: 0.8;
  color: var(--button-text);
  border-radius: var(--button-radius);
  height: var(--button-size);
  background-color: unset;

  &:hover {
    color: var(--button-text-hover-lit);
  }
  &:active {
    color: var(--button-text-active-lit);
  }
`;

const LoginInputText = styled.input`
  appearance: none;
  border-radius: var(--item-radius);
  padding: var(--item-padding);
  border-right-style: none;
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
`;

const LoginSubmit = styled.input`
  appearance: none;
  border-radius: var(--item-radius);
  border-left-style: none;
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
  padding: var(--item-padding);
  cursor: pointer;
  color: var(--main-text);
  background-color: var(--button-background);

  &:hover {
    background-color: var(--button-hover);
  }
  &:active {
    background-color: var(--button-active);
  }
`;

interface UserMenuProps extends ConnectUser {
  userActions: UserActions;
}

type UserMenuState = {
  loginValue: string;
  isMenuOpen: boolean;
  awaitFocus: boolean;
};

class UserMenu extends PureComponent<UserMenuProps, UserMenuState> {
  private readonly inputTextRef: React.RefObject<HTMLInputElement>;

  constructor(props: UserMenuProps) {
    super(props);
    this.state = {
      loginValue: '',
      isMenuOpen: false,
      awaitFocus: false,
    };
    this.inputTextRef = React.createRef();
  }

  componentDidMount(): void {
    this.componentDidUpdate();
  }

  componentDidUpdate(): void {
    const { awaitFocus } = this.state;
    if (awaitFocus && this.inputTextRef.current) {
      this.inputTextRef.current.focus();
      this.setState({ awaitFocus: false });
    }
  }

  private closeMenu(): void {
    this.setState({
      loginValue: '',
      isMenuOpen: false,
    });
  }

  handleMenuClick = (event: React.MouseEvent<HTMLElement>): void => {
    const { isMenuOpen } = this.state;
    this.setState({ isMenuOpen: !isMenuOpen });
    event.preventDefault();
  };

  handleUserClick = (event: React.MouseEvent<HTMLElement>): void => {
    const { user, dispatch } = this.props;
    if (user !== undefined) {
      const { userId } = user;
      dispatch(initUser({ userId }));
      this.closeMenu();
    }
    event.preventDefault();
  };

  handleTopicClick = (event: React.MouseEvent<HTMLElement>): void => {
    const { dispatch } = this.props;
    dispatch(initTopic({}));
    this.closeMenu();
    event.preventDefault();
  };

  handleLoginClick = (event: React.MouseEvent<HTMLElement>): void => {
    const { dispatch } = this.props;
    dispatch(setModal({ activeModal: ActiveModal.Login }));
    event.preventDefault();
  };

  handleLogoutClick = (event: React.MouseEvent<HTMLElement>): void => {
    const { userActions, user } = this.props;
    if (user !== undefined) {
      userActions.logout(user.token).then(
        (success) => {
          if (!success) {
            console.warn('logout was not successful!');
          }
          const { dispatch } = this.props;
          dispatch(setUser({ user: undefined }));
          dispatch(setModal({ activeModal: ActiveModal.None }));
          this.closeMenu();
        },
        (e) => {
          errHnd(e);
        },
      );
    }
    event.preventDefault();
  };

  handleChange = (event: React.FormEvent<HTMLInputElement>): void => {
    this.setState({ loginValue: event.currentTarget.value });
  };

  handleSubmit = (event: React.FormEvent<HTMLFormElement>): void => {
    const { userActions } = this.props;
    const { loginValue } = this.state;
    userActions.login(loginValue as Username).then(
      (user) => {
        const { dispatch } = this.props;
        dispatch(setUser({ user }));
        dispatch(setModal({ activeModal: ActiveModal.None }));
      },
      (e) => {
        errHnd(e);
      },
    );
    event.preventDefault();
  };

  onLoginOpen = (): void => {
    this.closeMenu();
    this.setState({ awaitFocus: true });
  };

  render(): ReactNode {
    const { user } = this.props;
    const isLoggedIn = user !== undefined;
    const { isMenuOpen, loginValue } = this.state;
    const username = isLoggedIn ? user.name : undefined;
    return (
      <Menu>
        <MenuItem>
          <MenuButton onClick={this.handleMenuClick}>≡</MenuButton>
          {!isMenuOpen || isLoggedIn ? (
            <MenuItemButton
              onClick={
                isLoggedIn ? this.handleUserClick : this.handleLoginClick
              }>
              {isLoggedIn ? username : 'Sign In'}
            </MenuItemButton>
          ) : (
            <Pad />
          )}
        </MenuItem>
        {isMenuOpen ? (
          <React.Fragment>
            <MenuItem>
              <MenuItemButton onClick={this.handleTopicClick}>
                Topics
              </MenuItemButton>
            </MenuItem>
            <MenuItem>
              {isLoggedIn ? (
                <MenuItemButton onClick={this.handleLogoutClick}>
                  ⇥ Logout
                </MenuItemButton>
              ) : (
                <MenuItemButton onClick={this.handleLoginClick}>
                  Sign In
                </MenuItemButton>
              )}
            </MenuItem>
          </React.Fragment>
        ) : null}
        <Modal
          modalTrigger={ActiveModal.Login}
          header="Welcome back!"
          footer="Sign in to be able to vote and write messages."
          onOpen={this.onLoginOpen}>
          <form onSubmit={this.handleSubmit}>
            <label>
              Name:&nbsp;
              <LoginInputText
                type="text"
                value={loginValue}
                ref={this.inputTextRef}
                onChange={this.handleChange}
              />
            </label>
            <LoginSubmit
              type="submit"
              value="Login"
            />
          </form>
        </Modal>
      </Menu>
    );
  }
} // UserMenu

const connector = connect((state: RootState) => ({
  user: state.userState.currentUser,
}));

export default connector(UserMenu);

type ConnectUser = ConnectedProps<typeof connector>;
