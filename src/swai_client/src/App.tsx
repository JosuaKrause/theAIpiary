import { PureComponent } from 'react';
import styled from 'styled-components';

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

type AppProps = Record<string, never>;
type AppState = Record<string, never>;

export default class App extends PureComponent<AppProps, AppState> {
  // private readonly userActions: UserActions;

  constructor(props: AppProps) {
    super(props);
    this.state = {};
    // this.userActions = new UserActions(undefined);
  }

  render() {
    return (
      <Main>
        {/* <MainColumn>
          <View
            graph={this.graph}
            userActions={this.userActions}
          />
        </MainColumn> */}
        {/* <UserMenu userActions={this.userActions} /> */}
      </Main>
    );
  }
} // App
