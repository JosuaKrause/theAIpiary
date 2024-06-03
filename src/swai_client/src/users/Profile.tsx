/**
 * Copyright (c) 2024 Josua Krause - All Rights Reserved
 *
 * THE CONTENTS OF THIS PROJECT ARE PROPRIETARY AND CONFIDENTIAL.
 * UNAUTHORIZED COPYING, TRANSFERRING OR REPRODUCTION OF THE CONTENTS OF
 * THIS PROJECT, VIA ANY MEDIUM IS STRICTLY PROHIBITED.
 *
 * The receipt or possession of the source code and/or any parts thereof does
 * not convey or imply any right to use them for any purpose other than the
 * purpose for which they were provided to you.
 *
 * The software is provided "AS IS", without warranty of any kind, express or
 * implied, including but not limited to the warranties of merchantability,
 * fitness for a particular purpose and non infringement. In no event shall the
 * authors or copyright holders be liable for any claim, damages or other
 * liability, whether in an action of contract, tort or otherwise, arising
 * from, out of or in connection with the software or the use or other dealings
 * in the software.
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the software.
 */
import React, {
  ChangeEventHandler,
  MouseEventHandler,
  PureComponent,
} from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled, { css } from 'styled-components';
import {
  ApiUserCapability,
  DisplayName,
  SessionInfo,
  UserEmail,
  UserInfo,
  WorkerInfo,
  WorkerStatus,
  WorkerToken,
  toCapabilityList,
} from '../api/types';
import { StaticMarkdown } from '../misc/Markdown';
import { redirectWelcome } from '../misc/common';
import { WORKER_UPDATE } from '../misc/constants';
import { RootState } from '../store';
import AutoHide from './AutoHide';
import Discord from './Discord';
import Logo from './Logo';
import UserActions from './UserActions';

const VMain = styled.div`
  min-width: 40vw;
  max-width: 60vw;
  height: fit-content;
  padding-bottom: 40px;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
    max-width: 100vw;
  }
`;

const HeaderRow = styled.div`
  margin: 20px 0;
  padding-top: 20px;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
`;

const HeaderBand = styled.div`
  margin-left: 5px;
  padding-left: 5px;
  display: flex;
  flex-direction: row;
  justify-content: left;
`;

const Header = styled.h3`
  text-align: left;
  align-self: center;
  padding-left: 10px;
`;

const Label = styled.label`
  flex-grow: 0;
  padding: 5px;
`;

const InputText = styled.input`
  appearance: none;
  padding: var(--item-padding);
  flex-grow: 0;
  padding: 5px;
  margin: 2px;
`;

const Link = styled.a`
  width: 100%;
  font-weight: bold;
  color: silver;
  text-decoration: none;
  text-align: left;

  &:visited {
    color: silver;
  }

  &:hover {
    color: lightgray;
    background-color: var(--button-background);
  }
`;

const SessionLink = styled.a`
  width: 100%;
  max-width: 100%;
  overflow: hidden;
  font-weight: bold;
  color: silver;
  text-decoration: none;
  text-align: left;
  white-space: nowrap;

  &:visited {
    color: silver;
  }

  &:hover {
    color: lightgray;
    background-color: var(--button-background);
  }
`;

const Button = styled.input`
  appearance: none;
  border-radius: var(--item-padding);
  padding: var(--item-padding);
  cursor: pointer;
  color: var(--main-text);
  background-color: var(--button-background);
  flex-grow: 0;

  &:hover {
    background-color: var(--button-hover);
  }
  &:active {
    background-color: var(--button-active);
  }
`;

const STATUS_COLOR_MAP: { [key in WorkerStatus]: string } = {
  unknown: 'darkgray',
  idle: 'green',
  busy: 'cornflowerblue',
  backedup: 'yellow',
  offline: 'crimson',
};

type StatusProps = {
  status: WorkerStatus;
};
const Status = styled.span<StatusProps>`
  display: inline-block;
  width: 1.2em;
  height: 1.2em;
  border-radius: 0.6em;
  vertical-align: middle;
  transform: translate(0, -0.15em);
  background-color: ${({ status }) => STATUS_COLOR_MAP[status]};
`;

type GroupProps = {
  maxHeight?: number;
};

function styleGroup(maxHeight: number | undefined) {
  if (maxHeight === undefined) {
    return css``;
  }
  return css`
    max-height: ${maxHeight}px;
    overflow: auto;
  `;
}

const Group = styled.fieldset<GroupProps>`
  margin: 5px;
  padding: 5px;
  border: 1px solid darkgray;
  min-width: 0;
  width: 100%;

  ${({ maxHeight }) => styleGroup(maxHeight)}

  @media (hover: none) and (max-width: 480px) {
    width: calc(100vw - 10px);
    margin-right: 0;
  }
`;

const GroupTitle = styled.legend`
  text-align: left;
  padding: 5px;
`;

const SessionGroup = styled.fieldset<GroupProps>`
  margin: 5px;
  padding: 5px;
  border: 1px solid darkgray;
  width: 100%;
  min-width: 0;
  max-width: 60vw;

  ${({ maxHeight }) => styleGroup(maxHeight)}

  overflow-x: hidden;

  @media (hover: none) and (max-width: 480px) {
    width: calc(100vw - 10px);
    max-width: 100vw;
    margin-right: 0;
  }
`;

const SessionRow = styled.div`
  display: flex;
  flex-direction: row;
  justify-content: start;
`;

const UserEntry = styled.div`
  display: flex;
  flex-direction: column;
  justify-content: start;
  width: 100%;
`;

const UserRow = styled.div`
  width: 100%;
  max-width: 100%;
  overflow: hidden;

  color: silver;
  text-align: left;
  white-space: nowrap;
  cursor: pointer;

  &:hover {
    color: lightgray;
    background-color: var(--button-background);
  }
`;

type ClickableUserRowProps = {
  children: React.ReactNode;
  setSelectedUser: (email: Readonly<UserEmail> | null) => void;
  email: Readonly<UserEmail>;
  isSelected: boolean;
};

class ClickableUserRow extends PureComponent<ClickableUserRowProps> {
  onClick: MouseEventHandler<HTMLDivElement> = (e) => {
    if (e.isDefaultPrevented()) {
      return;
    }
    e.preventDefault();
    const { isSelected, setSelectedUser, email } = this.props;
    if (isSelected) {
      setSelectedUser(null);
    } else {
      setSelectedUser(email);
    }
  };

  render() {
    const { children } = this.props;
    return <UserRow onClick={this.onClick}>{children}</UserRow>;
  }
}

const CapabilityEntry = styled.div`
  display: flex;
  flex-direction: row;
  justify-content: end;
  width: 100%;
`;

const CapabilityLabel = styled.label`
  flex-grow: 0;
  cursor: pointer;

  &:hover {
    color: silver;
  }
`;

const CapabilityToggle = styled.input`
  padding: var(--item-padding);
  flex-grow: 0;
`;

type CapabilityToggleInputProps = {
  setCapability: (
    email: Readonly<UserEmail>,
    capability: ApiUserCapability,
    setActive: boolean,
    onDone: () => void,
  ) => void;
  email: Readonly<UserEmail>;
  capability: ApiUserCapability;
  isActive: boolean;
};
type CapabilityToggleInputState = {
  inFlight: boolean;
};

class CapabilityToggleInput extends PureComponent<
  CapabilityToggleInputProps,
  CapabilityToggleInputState
> {
  constructor(props: Readonly<CapabilityToggleInputProps>) {
    super(props);
    this.state = {
      inFlight: false,
    };
  }

  onChange: ChangeEventHandler<HTMLInputElement> = (e) => {
    if (e.isDefaultPrevented()) {
      return;
    }
    e.preventDefault();
    const { inFlight } = this.state;
    if (inFlight) {
      return;
    }
    const { isActive, setCapability, capability, email } = this.props;
    this.setState({ inFlight: true }, () => {
      setCapability(email, capability, !isActive, () => {
        this.setState({ inFlight: false });
      });
    });
  };

  render() {
    const { isActive } = this.props;
    const { inFlight } = this.state;
    return (
      <CapabilityToggle
        type="checkbox"
        checked={isActive}
        disabled={inFlight}
        onChange={this.onChange}
      />
    );
  }
}

const Row = styled.div`
  display: flex;
  flex-direction: row;
  justify-content: space-between;
`;

const RowSpan = styled.span`
  vertical-align: middle;
`;

const TextParagraph = styled.div`
  text-align: justified;
  margin-bottom: 10px;
`;

const RowParagraph = styled.p`
  text-align: left;
  width: 19vw;

  @media (hover: none) and (max-width: 480px) {
    width: 47vw;
  }
`;

interface ProfileProps extends ConnectProfile {
  userActions: UserActions;
  appName: string;
}
type EmptyProfileProps = {
  userActions: undefined;
};
type ProfileState = {
  initUsers: boolean;
  users: UserInfo[];
  initChats: boolean;
  chats: SessionInfo[];
  initWorkers: boolean;
  workers: WorkerInfo[];
  createdUserMessage: string | null;
  workerToken: Readonly<WorkerToken> | null;
  inFlightUserCreation: boolean;
  selectedUser: Readonly<UserEmail> | null;
};

class Profile extends PureComponent<ProfileProps, ProfileState> {
  private readonly createNameRef: React.RefObject<HTMLInputElement>;
  private readonly createEmailRef: React.RefObject<HTMLInputElement>;

  constructor(props: Readonly<ProfileProps>) {
    super(props);
    this.state = {
      initUsers: false,
      users: [],
      initChats: false,
      chats: [],
      initWorkers: false,
      workers: [],
      createdUserMessage: null,
      workerToken: null,
      inFlightUserCreation: false,
      selectedUser: null,
    };
    this.createNameRef = React.createRef();
    this.createEmailRef = React.createRef();
  }

  componentDidMount(): void {
    this.componentDidUpdate(
      { userActions: undefined },
      {
        initUsers: false,
        users: [],
        initChats: false,
        chats: [],
        initWorkers: false,
        workers: [],
        createdUserMessage: null,
        workerToken: null,
        inFlightUserCreation: false,
        selectedUser: null,
      },
    );
  }

  componentDidUpdate(
    _prevProps: Readonly<ProfileProps> | EmptyProfileProps,
    _prevState: Readonly<ProfileState>,
  ): void {
    const { userActions, user } = this.props;
    const { initUsers, initChats, initWorkers } = this.state;
    if (!initUsers && user && user.capabilities.listUsers) {
      this.setState(
        {
          initUsers: true,
        },
        () =>
          userActions.getUsers((users) => {
            this.setState({ users });
          }),
      );
    }
    if (!initChats) {
      this.setState(
        {
          initChats: true,
        },
        () =>
          userActions.getChats((chats) => {
            this.setState({ chats });
          }),
      );
    }
    if (!initWorkers) {
      this.setState(
        {
          initWorkers: true,
        },
        () =>
          userActions.getWorkers((workers) => {
            this.setState({ workers });
            setTimeout(() => {
              this.setState({ initWorkers: false });
            }, WORKER_UPDATE);
          }),
      );
    }
  }

  handleWorkerTokenClick: MouseEventHandler<HTMLInputElement> = (e) => {
    e.preventDefault();
    const { userActions } = this.props;
    userActions.getWorkerToken((workerToken) => {
      this.setState({ workerToken });
    });
  };

  handleLogoutClick: MouseEventHandler<HTMLInputElement> = (e) => {
    e.preventDefault();
    const { userActions } = this.props;
    userActions.logout((user) => {
      if (!user.logged) {
        redirectWelcome();
      }
    });
  };

  handleCreateUserClick: MouseEventHandler<HTMLInputElement> = (e) => {
    e.preventDefault();
    const { userActions } = this.props;
    const emailInput = this.createEmailRef.current;
    const nameInput = this.createNameRef.current;
    if (!emailInput || !nameInput) {
      return;
    }
    const email = emailInput.value as UserEmail;
    const displayName = nameInput.value as DisplayName;
    if (!email || !email.length || !displayName || !displayName.length) {
      this.setState({
        createdUserMessage: 'Please provide an email and a name!',
      });
      return;
    }
    const { inFlightUserCreation } = this.state;
    if (inFlightUserCreation) {
      this.setState({
        createdUserMessage:
          "Clicking the button multiple times won't make it go faster!",
      });
      return;
    }
    this.setState(
      {
        inFlightUserCreation: true,
      },
      () => {
        userActions.createUser(email, displayName, (newEmail) => {
          if (newEmail) {
            emailInput.value = '';
            nameInput.value = '';
            this.setState({
              createdUserMessage: `Sent email to: ${newEmail}`,
              initUsers: false,
            });
          } else {
            this.setState({ createdUserMessage: 'Could not create user!' });
          }
          this.setState({
            inFlightUserCreation: false,
          });
        });
      },
    );
  };

  setSelectedUser = (email: Readonly<UserEmail> | null) => {
    this.setState({
      selectedUser: email,
    });
  };

  setCapability = async (
    email: Readonly<UserEmail>,
    capability: ApiUserCapability,
    setActive: boolean,
    onDone: () => void,
  ) => {
    const { userActions } = this.props;
    await userActions.changeCapability(email, capability, setActive, () => {
      this.setState({ initUsers: false }, () => {
        onDone();
      });
    });
  };

  render() {
    const { user, appName } = this.props;
    const {
      workerToken,
      createdUserMessage,
      users,
      chats,
      workers,
      selectedUser,
    } = this.state;
    return (
      <VMain>
        <HeaderRow>
          <HeaderBand>
            <Logo appName={appName} />
            <Header>
              Welcome, {user?.displayName} (
              <AutoHide title="@">{user?.email}</AutoHide>)
            </Header>
          </HeaderBand>
          <Discord />
        </HeaderRow>
        {chats.length ? (
          <SessionGroup maxHeight={200}>
            <GroupTitle>Chats</GroupTitle>
            {chats.map(({ session: chatId, summary }) => (
              <SessionRow key={`${chatId}`}>
                <SessionLink href={`/chat?session=${chatId}`}>
                  {summary ? summary : `Chat (${chatId})`}
                </SessionLink>
              </SessionRow>
            ))}
          </SessionGroup>
        ) : null}
        <Group>
          <Row>
            <Link href="/chat">Start New Chat...</Link>
          </Row>
        </Group>
        {users.length ? (
          <Group maxHeight={200}>
            <GroupTitle>Users</GroupTitle>
            {users.map((userEntry) => {
              const { email, displayName } = userEntry;
              const isSelected = email === selectedUser;
              const rowKey = `${email}`.replaceAll(/[^a-zA-Z_0-9-]/g, '_');
              return (
                <Row key={rowKey}>
                  <UserEntry>
                    <ClickableUserRow
                      email={email}
                      isSelected={isSelected}
                      setSelectedUser={this.setSelectedUser}>
                      {displayName} (<AutoHide title="@">{email}</AutoHide>)
                    </ClickableUserRow>
                    {isSelected && user && user.capabilities.changeCapabilities
                      ? toCapabilityList(userEntry).map(
                          ({ name: capName, has: capHas }) => {
                            const capKey = `${rowKey}_${capName}`;
                            return (
                              <CapabilityEntry key={capKey}>
                                <CapabilityLabel>
                                  {capName}
                                  <CapabilityToggleInput
                                    isActive={capHas}
                                    capability={capName}
                                    email={email}
                                    setCapability={this.setCapability}
                                  />
                                </CapabilityLabel>
                              </CapabilityEntry>
                            );
                          },
                        )
                      : null}
                  </UserEntry>
                </Row>
              );
            })}
          </Group>
        ) : null}
        {user && user.capabilities.createUser ? (
          <Group>
            <GroupTitle>Create User</GroupTitle>
            <Row>
              <Label htmlFor="createemail">New User Email:</Label>
              <InputText
                autoComplete="off"
                name="createemail"
                type="text"
                ref={this.createEmailRef}
              />
            </Row>
            <Row>
              <Label htmlFor="createdisplay">New User Display Name:</Label>
              <InputText
                autoComplete="off"
                name="createdisplay"
                type="text"
                ref={this.createNameRef}
              />
            </Row>
            <Row>
              <Button
                name="createuser"
                type="button"
                value="Create User"
                onClick={this.handleCreateUserClick}
              />
            </Row>
            {createdUserMessage ? <Row>{createdUserMessage}</Row> : null}
          </Group>
        ) : null}
        {workers.length ? (
          <Group maxHeight={200}>
            <GroupTitle>Worker Bees</GroupTitle>
            {workers.map(({ own, workerId, email, status }) => (
              <Row key={`${workerId}`}>
                <RowSpan>
                  {own ? <strong>{workerId}</strong> : workerId}
                  {email ? (
                    <React.Fragment>
                      {' '}
                      (<AutoHide title="@">{email}</AutoHide>)
                    </React.Fragment>
                  ) : null}
                </RowSpan>
                <RowSpan>
                  {status} <Status status={status} />
                </RowSpan>
              </Row>
            ))}
          </Group>
        ) : null}
        {user && user.capabilities.registerOwnWorker ? (
          <Group>
            <GroupTitle>Add Worker Bees</GroupTitle>
            <Row>
              <AutoHide title="➤ Add your GPU to the Swarm">
                <TextParagraph>
                  <StaticMarkdown
                    appName={appName}
                    url="/docs/worker.md"
                  />
                </TextParagraph>
              </AutoHide>
            </Row>
            <Row>
              <AutoHide title="➤ Get Worker Token">
                <RowParagraph>
                  Creating a new worker token will disconnect all your current
                  worker bees!
                </RowParagraph>
                <Button
                  name="workertoken"
                  type="button"
                  value="Replace Worker Token"
                  onClick={this.handleWorkerTokenClick}
                />
              </AutoHide>
            </Row>
            {workerToken ? (
              <Row>
                Worker Token: <pre>{workerToken}</pre>
              </Row>
            ) : null}
          </Group>
        ) : null}
        <Group>
          <Row>
            <Button
              name="logout"
              type="button"
              value="Logout"
              onClick={this.handleLogoutClick}
            />
          </Row>
        </Group>
      </VMain>
    );
  }
} // Profile

const connector = connect((state: RootState) => ({
  user: state.userState.currentUser,
}));

export default connector(Profile);

type ConnectProfile = ConnectedProps<typeof connector>;
