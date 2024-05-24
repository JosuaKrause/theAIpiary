import { MouseEventHandler, PureComponent } from 'react';
import styled from 'styled-components';
import { WorkerToken } from '../api/types';
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

type ProfileProps = {
  userActions: UserActions;
};
type ProfileState = {
  workerToken: Readonly<WorkerToken> | null;
};

export default class Profile extends PureComponent<
  ProfileProps,
  ProfileState
> {
  constructor(props: Readonly<ProfileProps>) {
    super(props);
    this.state = { workerToken: null };
  }

  handleClick: MouseEventHandler<HTMLInputElement> = (e) => {
    e.preventDefault();
    const { userActions } = this.props;
    userActions.getWorkerToken((workerToken) => {
      this.setState({ workerToken });
    });
  };

  render() {
    const { workerToken } = this.state;
    return (
      <VMain>
        <input
          name="workertoken"
          type="button"
          value="Get Worker Token"
          onClick={this.handleClick}
        />
        <div>
          Worker Token: <pre>{workerToken}</pre>
        </div>
      </VMain>
    );
  }
} // Login
