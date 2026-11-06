/**
 * Copyright (C) 2024 Josua Krause
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import { BrowserRouter, Route, Routes } from 'react-router';
import styled from 'styled-components';
import { SessionId } from './api/types';
import Chat from './chat/Chat';
import ChatActions from './chat/ChatActions';
import { setSession } from './chat/ChatStateSlice';
import Welcome from './general/Welcome';
import { StaticMarkdown } from './misc/Markdown';
import { RootState } from './store';
import Login from './users/Login';
import Profile from './users/Profile';
import ResetPassword from './users/ResetPassword';
import UserActions from './users/UserActions';
import UserButton from './users/UserButton';

const Main = styled.div`
  margin: 0 auto;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--main-background);
  color: var(--main-text);
`;

const HMain = styled.div`
  display: flex;
  justify-content: center;
  min-height: 100vh;
  max-width: 100vw;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
    align-items: start;
    flex-direction: column-reverse;
  }
`;

const VMain = styled.div`
  display: flex;
  flex-direction: column;
  justify-content: start;
  min-height: 100vh;
`;

const FullText = styled.div`
  align-self: center;
  flex-grow: 0;
  text-align: justify;
  margin: 10px;
  padding: 5px;
  max-width: 42vw;

  @media (hover: none) and (max-width: 480px) {
    max-width: 100vw;
  }
`;

interface AppProps extends ConnectApp {
  appName: string;
}

type AppState = {
  ready: boolean;
};

type HistoryState = {
  session: SessionId | undefined;
};

class App extends PureComponent<AppProps, AppState> {
  private readonly chatActions: ChatActions;
  private readonly userActions: UserActions;

  constructor(props: AppProps) {
    super(props);
    this.state = {
      ready: false,
    };
    this.chatActions = new ChatActions(undefined);
    this.userActions = new UserActions(undefined);

    window.addEventListener('popstate', (event) => {
      const { dispatch } = this.props;
      const state: HistoryState = event.state;
      const { session } = state;
      dispatch(setSession({ session }));
    });
  }

  componentDidMount(): void {
    const { dispatch } = this.props;
    const { ready } = this.state;
    const params = new URL(window.location.href).searchParams;
    const session = params.get('session') as SessionId | null;
    if (session) {
      dispatch(setSession({ session }));
    } else if (!ready) {
      this.setState({ ready: true });
    }
  }

  componentDidUpdate(
    prevProps: Readonly<AppProps>,
    _prevState: Readonly<AppState>,
  ): void {
    const { ready } = this.state;
    const { session } = this.props;
    const { session: prevSession } = prevProps;
    if (!ready) {
      if (session) {
        this.setState({ ready: true });
      }
    } else if (session !== prevSession) {
      const history = window.history;
      const params = new URLSearchParams(
        new URL(window.location.href).searchParams,
      );
      if (session) {
        params.set('session', `${session}`);
      } else {
        params.delete('session');
      }
      const url = new URL(window.location.href);
      url.search = params.toString();
      if (prevSession) {
        history.pushState({ session }, '', url);
      } else {
        history.replaceState({ session }, '', url);
      }
    }
  }

  render() {
    const { appName, user } = this.props;
    const { ready } = this.state;
    return (
      <Main>
        <HMain>
          <BrowserRouter>
            <Routes>
              <Route
                path="/chat"
                element={
                  <UserButton
                    userActions={this.userActions}
                    redirect={true}
                    show={true}>
                    <Chat
                      ready={ready}
                      chatActions={this.chatActions}
                    />
                  </UserButton>
                }
              />
              <Route
                path="/login"
                element={<Login userActions={this.userActions} />}
              />
              <Route
                path="/reset-password"
                element={<ResetPassword userActions={this.userActions} />}
              />
              <Route
                path="/profile"
                element={
                  <UserButton
                    userActions={this.userActions}
                    redirect={true}
                    show={false}>
                    <Profile
                      appName={appName}
                      userActions={this.userActions}
                    />
                  </UserButton>
                }
              />
              <Route
                path="/faq"
                element={
                  <VMain>
                    <UserButton
                      userActions={this.userActions}
                      redirect={false}
                      show={false}>
                      <FullText>
                        <StaticMarkdown
                          appName={appName}
                          backLink={user ? '/profile' : '/'}
                          url="/docs/faq.md"
                        />
                      </FullText>
                    </UserButton>
                  </VMain>
                }
              />
              <Route
                path="/"
                element={
                  <UserButton
                    userActions={this.userActions}
                    redirect={false}
                    show={false}>
                    <Welcome appName={appName} />
                  </UserButton>
                }
              />
            </Routes>
          </BrowserRouter>
        </HMain>
      </Main>
    );
  }
} // App

const connector = connect((state: RootState) => ({
  session: state.chatState.currentSession,
  user: state.userState.currentUser,
}));

export default connector(App);

type ConnectApp = ConnectedProps<typeof connector>;
