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
import { redirectLogin } from '../misc/common';

export type UserEmail = string & { _userEmail: void };
export type DisplayName = string & { _displayName: void };
export type Password = string & { _password: void };
export type SessionId = string & { _sessionId: void };
export type TaskId = string & { _taskId: void };
export type ResetToken = string & { _resetToken: void };
export type WorkerToken = string & { _workerToken: void };
type WorkerId = string & { _workerId: void };

export type Role = 'assistant' | 'user';

type TaskStatus =
  | 'init'
  | 'wait'
  | 'busy'
  | 'ready'
  | 'done'
  | 'deferred'
  | 'error'
  | 'unknown';

export type WorkerStatus =
  'unknown' | 'idle' | 'busy' | 'backedup' | 'offline';

export type Thinking = 'inactive' | 'thinking' | 'queued' | 'error';
export const ACTIVE_THINKING: Thinking[] = ['thinking', 'queued'];

export type Message = {
  role: Role;
  content: string;
};

export type ApiChatInitResponse = {
  model_session: SessionId;
  messages: Message[];
};
export type ChatInitResponse = {
  session: SessionId;
  messages: Message[];
};

export type ChatRecoverResponse = {
  messages: Message[];
  task: TaskId | undefined;
  status: TaskStatus;
};

export type ApiChatPromptResponse = {
  task: TaskId | undefined;
  status: TaskStatus;
};
type ChatPromptError = {
  error: true;
  message: string;
};
type ChatPromptTask = {
  error: false;
  task: TaskId | undefined;
  status: TaskStatus;
};
export type ChatPromptResponse = ChatPromptError | ChatPromptTask;

export type ApiChatTextResponse = {
  diff: string;
  task: Readonly<TaskId> | undefined;
  next_index: number | undefined;
  status: TaskStatus;
};
export type ChatTextResponse = {
  diff: string;
  nextTask: Readonly<TaskId> | undefined;
  nextIndex: number | undefined;
  status: TaskStatus;
};

type ApiSessionInfo = {
  model_session: SessionId;
  time: string | undefined;
  summary: string | undefined;
};
export type SessionInfo = {
  session: SessionId;
  time: string | undefined;
  summary: string | undefined;
};
export type ApiChatSessionsResponse = {
  model_sessions: ApiSessionInfo[];
};

export type UserCapabilities = {
  changeCapabilities: Readonly<boolean>;
  logoutOtherUser: Readonly<boolean>;
  createUser: Readonly<boolean>;
  deleteUser: Readonly<boolean>;
  listUsers: Readonly<boolean>;
  registerOwnWorker: Readonly<boolean>;
  registerOtherWorker: Readonly<boolean>;
};
export type User = {
  logged: true;
  email: Readonly<UserEmail>;
  displayName: Readonly<DisplayName>;
  capabilities: Readonly<UserCapabilities>;
  discord: Readonly<string> | undefined;
};
export type LoginInfo = {
  logged: false;
  message: string;
};

export type ApiUserCapability =
  | 'change_capabilities'
  | 'logout_other_user'
  | 'create_user'
  | 'delete_user'
  | 'list_users'
  | 'register_own_worker'
  | 'register_other_worker';
export type ApiLoginResponse =
  | {
      logged: true;
      email: Readonly<UserEmail>;
      display_name: Readonly<DisplayName>;
      capabilities: Readonly<ApiUserCapability[]>;
      discord: Readonly<string> | undefined;
    }
  | {
      logged: false;
      message: string;
    };

export type ApiPasswordResetTokenResponse = {
  email: Readonly<UserEmail> | undefined;
};

export type ApiChangeCapability = {
  okay: boolean;
  capabilities: Readonly<ApiUserCapability[]>;
};

export type ApiSendResetResponse = {
  email: Readonly<UserEmail>;
  sent: boolean;
};

export type ApiDeleteUserResponse = {
  email: Readonly<UserEmail>;
  deleted: boolean;
  chats: number;
};
export type DeleteUserResult = {
  deleted: boolean;
  chats: number;
};

type ApiUserInfoResponse = {
  email: Readonly<UserEmail>;
  display_name: Readonly<DisplayName>;
  capabilities: Readonly<ApiUserCapability[]>;
  admin: boolean;
};
export type ApiUserListResponse = {
  users: ApiUserInfoResponse[];
};
export type UserInfo = {
  email: Readonly<UserEmail>;
  displayName: Readonly<DisplayName>;
  capabilities: Readonly<UserCapabilities>;
  isAdmin: boolean;
};

export type WorkerInfo = {
  workerId: Readonly<WorkerId>;
  email: Readonly<UserEmail> | undefined;
  status: WorkerStatus;
  own: boolean;
};
type ApiWorkerInfo = {
  worker_id: Readonly<WorkerId>;
  email: Readonly<UserEmail> | undefined;
  status: WorkerStatus;
  own: boolean;
};
export type ApiWorkerInfoResponse = {
  workers: ApiWorkerInfo[];
};

export type ApiWorkerTokenResponse = {
  worker_token: Readonly<WorkerToken>;
};

const NO_CAPABILITIES: Readonly<UserCapabilities> = {
  changeCapabilities: false,
  logoutOtherUser: false,
  createUser: false,
  deleteUser: false,
  listUsers: false,
  registerOwnWorker: false,
  registerOtherWorker: false,
};

type CapabilityMapping = {
  [key in keyof UserCapabilities]: ApiUserCapability;
};

const CAPABILITY_MAP: CapabilityMapping = {
  changeCapabilities: 'change_capabilities',
  logoutOtherUser: 'logout_other_user',
  createUser: 'create_user',
  deleteUser: 'delete_user',
  listUsers: 'list_users',
  registerOwnWorker: 'register_own_worker',
  registerOtherWorker: 'register_other_worker',
};

type CapabilityItem = {
  name: ApiUserCapability;
  has: boolean;
};

export function toCapabilityList(user: UserInfo): CapabilityItem[] {
  const { capabilities } = user;
  let capKey: keyof UserCapabilities;
  const res = [];
  for (capKey in capabilities) {
    res.push({
      name: CAPABILITY_MAP[capKey],
      has: capabilities[capKey],
    });
  }
  return res;
}

export function toUserCapabilities(
  caps: Readonly<ApiUserCapability[]>,
): UserCapabilities {
  const capabilities: UserCapabilities = { ...NO_CAPABILITIES };
  caps.forEach((cap) => {
    switch (cap) {
      case 'change_capabilities':
        capabilities.changeCapabilities = true;
        break;
      case 'logout_other_user':
        capabilities.logoutOtherUser = true;
        break;
      case 'create_user':
        capabilities.createUser = true;
        break;
      case 'delete_user':
        capabilities.deleteUser = true;
        break;
      case 'list_users':
        capabilities.listUsers = true;
        break;
      case 'register_own_worker':
        capabilities.registerOwnWorker = true;
        break;
      case 'register_other_worker':
        capabilities.registerOtherWorker = true;
        break;
    }
  });
  return capabilities;
}

export function toUserOrMessage(
  userResp: Readonly<ApiLoginResponse>,
): Readonly<User> | LoginInfo {
  const { logged } = userResp;
  if (!logged) {
    const { message } = userResp;
    return { logged: false, message };
  }
  const {
    capabilities: caps,
    email,
    display_name: displayName,
    discord,
  } = userResp;
  return {
    logged: true,
    email,
    displayName,
    capabilities: toUserCapabilities(caps),
    discord,
  };
}

export function checkResponse(res: Response) {
  if (res.ok) {
    return;
  }
  if (res.status === 401) {
    redirectLogin();
  }
  throw new Error(
    `Error in request ${res} (${res.status}): ${res.statusText}`,
  );
}
