import React, { FormEventHandler, PureComponent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import styled from 'styled-components';
import { Password, UserName } from '../api/types';
import UserActions from './UserActions';

const VMain = styled.div`
  display: flex;
  justify-content: center;
  flex-direction: column;
  flex-grow: 1;
  height: 100vh;
  max-height: 100vh;
  max-width: 60vw;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
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

type LoginProps = {
  userActions: UserActions;
};
type LoginState = Record<string, void>;

export default class Login extends PureComponent<LoginProps, LoginState> {
  private readonly nameRef: React.RefObject<HTMLInputElement>;
  private readonly passwordRef: React.RefObject<HTMLInputElement>;

  constructor(props: Readonly<LoginProps>) {
    super(props);
    this.state = {};
    this.nameRef = React.createRef();
    this.passwordRef = React.createRef();
  }

  componentDidMount(): void {
    this.componentDidUpdate(undefined, undefined);
  }

  componentDidUpdate(
    _prevProps: Readonly<LoginProps> | undefined,
    _prevState: Readonly<LoginState> | undefined,
  ) {
    const nameInput = this.nameRef.current;
    if (nameInput) {
      const [params, setParams] = useSearchParams();
      const user = params.get('user');
      if (user) {
        nameInput.value = user;
        params.delete('user');
        setParams(params, { replace: true });
      }
    }
  }

  handleSubmit: FormEventHandler<HTMLFormElement> = () => {
    const nameInput = this.nameRef.current;
    const passwordInput = this.passwordRef.current;
    if (!nameInput || !passwordInput) {
      return;
    }
    const userName = nameInput.value as UserName;
    const password = passwordInput.value as Password;
    const { userActions } = this.props;
    userActions.login(userName, password, (user) => {
      const navigate = useNavigate();
      if (user) {
        navigate('/chat');
      }
    });
  };

  render() {
    return (
      <VMain>
        <form onSubmit={this.handleSubmit}>
          <label>
            Name:&nbsp;
            <LoginInputText
              autoComplete="username"
              name="username"
              type="text"
              ref={this.nameRef}
            />
          </label>
          <label>
            Password:&nbsp;
            <LoginInputText
              autoComplete="password"
              name="password"
              type="password"
              ref={this.passwordRef}
            />
          </label>
          <LoginSubmit
            type="submit"
            value="Login"
          />
        </form>
      </VMain>
    );
  }
} // Login
