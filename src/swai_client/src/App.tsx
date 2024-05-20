import { PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled from 'styled-components';
import { SessionId } from './api/types';
import Chat from './chat/Chat';
import ChatActions from './chat/ChatActions';
import { setSession } from './chat/ChatStateSlice';
import { RootState } from './store';

const Main = styled.div`
  text-align: center;
  margin: 0 auto;
  height: 100vh;
  width: 100vw;
  display: flex;
  flex-direction: column;
  background-color: var(--main-background);
  color: var(--main-text);
`;

const HMain = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  max-width: 100vw;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
    align-items: start;
    flex-direction: column-reverse;
  }
`;

// const MainColumn = styled.div`
//   margin: 0 auto;
//   width: var(--main-size);
//   height: 100vh;
//   border: 0;
//   display: flex;
//   flex-direction: column;
//   flex-grow: 0;
//   overflow: hidden;
// `;

type AppProps = ConnectApp;

type AppState = {
  ready: boolean;
};

type HistoryState = {
  session: SessionId | undefined;
};

class App extends PureComponent<AppProps, AppState> {
  private readonly chatActions: ChatActions;

  constructor(props: AppProps) {
    super(props);
    this.state = {
      ready: false,
    };
    this.chatActions = new ChatActions(undefined);

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
    console.log(ready, session);
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
    console.log(ready, session);
    if (!ready) {
      if (session) {
        this.setState({ ready: true });
      }
    } else if (session !== prevSession) {
      const history = window.history;
      const params = new URLSearchParams();
      if (session) {
        params.set('session', `${session}`);
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
    const { ready } = this.state;
    return (
      <Main>
        <HMain>
          <Chat
            ready={ready}
            chatActions={this.chatActions}
          />
        </HMain>
      </Main>
    );
  }
} // App

const connector = connect((state: RootState) => ({
  session: state.chatState.currentSession,
}));

export default connector(App);

type ConnectApp = ConnectedProps<typeof connector>;
