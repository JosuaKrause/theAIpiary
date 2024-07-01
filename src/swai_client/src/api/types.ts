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
  | 'unknown'
  | 'idle'
  | 'busy'
  | 'backedup'
  | 'offline';

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

type UserCapabilities = {
  changeCapabilities: Readonly<boolean>;
  logoutOtherUser: Readonly<boolean>;
  createUser: Readonly<boolean>;
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
};

type ApiUserInfoResponse = {
  email: Readonly<UserEmail>;
  display_name: Readonly<DisplayName>;
  capabilities: Readonly<ApiUserCapability[]>;
};
export type ApiUserListResponse = {
  users: ApiUserInfoResponse[];
};
export type UserInfo = {
  email: Readonly<UserEmail>;
  displayName: Readonly<DisplayName>;
  capabilities: Readonly<UserCapabilities>;
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
