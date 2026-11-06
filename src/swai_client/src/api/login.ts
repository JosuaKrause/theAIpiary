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
import { URL_PREFIX } from '../misc/constants';
import {
  ApiChangeCapability,
  ApiChangeEmailResponse,
  ApiChatSessionsResponse,
  ApiDeleteUserResponse,
  ApiLoginResponse,
  ApiPasswordResetTokenResponse,
  ApiSendResetResponse,
  ApiUserCapability,
  ApiUserListResponse,
  ApiWorkerInfoResponse,
  ApiWorkerTokenResponse,
  DeleteUserResult,
  DisplayName,
  LoginInfo,
  Password,
  ResetToken,
  SessionInfo,
  User,
  UserCapabilities,
  UserEmail,
  UserInfo,
  WorkerInfo,
  WorkerToken,
  checkResponse,
  toUserCapabilities,
  toUserOrMessage,
} from './types';

export type LoginApiProvider = {
  getUser: () => Promise<Readonly<User> | Readonly<LoginInfo>>;
  newUser: (
    email: Readonly<UserEmail>,
    displayName: Readonly<DisplayName>,
  ) => Promise<Readonly<UserEmail> | undefined>;
  loginUser: (
    name: Readonly<UserEmail>,
    password: Readonly<Password>,
  ) => Promise<Readonly<User> | Readonly<LoginInfo>>;
  getResetPasswordToken: (
    name: Readonly<UserEmail>,
  ) => Promise<Readonly<UserEmail> | undefined>;
  resetPassword: (
    resetToken: Readonly<ResetToken>,
    password: Readonly<Password>,
  ) => Promise<Readonly<User> | Readonly<LoginInfo>>;
  changeCapability: (
    name: Readonly<UserEmail>,
    capability: ApiUserCapability,
    setActive: boolean,
  ) => Promise<UserCapabilities>;
  sendReset: (name: Readonly<UserEmail>) => Promise<boolean>;
  logoutUser: (name: Readonly<UserEmail>) => Promise<void>;
  deleteUser: (name: Readonly<UserEmail>) => Promise<DeleteUserResult>;
  changeEmail: (
    name: Readonly<UserEmail>,
    newEmail: Readonly<UserEmail>,
  ) => Promise<boolean>;
  logout: () => Promise<Readonly<User> | Readonly<LoginInfo>>;
  getWorkerToken: () => Promise<Readonly<WorkerToken>>;
  listUsers: () => Promise<UserInfo[]>;
  listChats: () => Promise<SessionInfo[]>;
  listWorkers: () => Promise<WorkerInfo[]>;
};

export const DEFAULT_LOGIN_API: LoginApiProvider = {
  getUser: async () => {
    const res = await fetch(`${URL_PREFIX}/user/current`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    checkResponse(res);
    const obj = (await res.json()) as ApiLoginResponse;
    return toUserOrMessage(obj);
  },
  newUser: async (email, displayName) => {
    const res = await fetch(`${URL_PREFIX}/user/create`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        new_email: email,
        new_display: displayName,
      }),
    });
    checkResponse(res);
    const { email: newEmail } =
      (await res.json()) as ApiPasswordResetTokenResponse;
    return newEmail;
  },
  loginUser: async (name, password) => {
    const res = await fetch(`${URL_PREFIX}/user/login`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        password,
      }),
    });
    checkResponse(res);
    const obj = (await res.json()) as ApiLoginResponse;
    return toUserOrMessage(obj);
  },
  getResetPasswordToken: async (name) => {
    const res = await fetch(`${URL_PREFIX}/user/reset_password_token`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
      }),
    });
    if (res.status === 403 || res.status === 401) {
      return undefined;
    }
    checkResponse(res);
    const { email } = (await res.json()) as ApiPasswordResetTokenResponse;
    return email;
  },
  resetPassword: async (resetToken, password) => {
    const res = await fetch(`${URL_PREFIX}/user/reset_password`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        reset_token: resetToken,
        password,
      }),
    });
    checkResponse(res);
    const obj = (await res.json()) as ApiLoginResponse;
    return toUserOrMessage(obj);
  },
  changeCapability: async (
    name: Readonly<UserEmail>,
    capability: ApiUserCapability,
    setActive: boolean,
  ) => {
    const res = await fetch(`${URL_PREFIX}/user/capability`, {
      method: 'PUT',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        capability,
        set_has: setActive,
      }),
    });
    checkResponse(res);
    const { capabilities } = (await res.json()) as ApiChangeCapability;
    return toUserCapabilities(capabilities);
  },
  sendReset: async (name) => {
    const res = await fetch(`${URL_PREFIX}/user/send_reset`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
      }),
    });
    checkResponse(res);
    const { sent } = (await res.json()) as ApiSendResetResponse;
    return sent;
  },
  logoutUser: async (name) => {
    const res = await fetch(`${URL_PREFIX}/user/logout`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
      }),
    });
    checkResponse(res);
    await res.json();
  },
  deleteUser: async (name) => {
    const res = await fetch(`${URL_PREFIX}/user/delete`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
      }),
    });
    checkResponse(res);
    const { deleted, chats } = (await res.json()) as ApiDeleteUserResponse;
    return { deleted, chats };
  },
  changeEmail: async (name, newEmail) => {
    const res = await fetch(`${URL_PREFIX}/user/change_email`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        new_email: newEmail,
      }),
    });
    checkResponse(res);
    const { changed } = (await res.json()) as ApiChangeEmailResponse;
    return changed;
  },
  logout: async () => {
    const res = await fetch(`${URL_PREFIX}/user/logout`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    checkResponse(res);
    const obj = (await res.json()) as ApiLoginResponse;
    return toUserOrMessage(obj);
  },
  getWorkerToken: async () => {
    const res = await fetch(`${URL_PREFIX}/user/create_worker_token`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    checkResponse(res);
    const { worker_token: workerToken } =
      (await res.json()) as ApiWorkerTokenResponse;
    return workerToken;
  },
  listUsers: async () => {
    const res = await fetch(`${URL_PREFIX}/user/list`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    checkResponse(res);
    const { users } = (await res.json()) as ApiUserListResponse;
    return users.map(({ email, display_name, capabilities, admin }) => ({
      email,
      displayName: display_name,
      capabilities: toUserCapabilities(capabilities),
      isAdmin: admin,
    }));
  },
  listChats: async () => {
    const res = await fetch(`${URL_PREFIX}/chat/list`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    checkResponse(res);
    const { model_sessions: sessions } =
      (await res.json()) as ApiChatSessionsResponse;
    return sessions.map(({ model_session, time, summary }) => ({
      session: model_session,
      time,
      summary,
    }));
  },
  listWorkers: async () => {
    const res = await fetch(`${URL_PREFIX}/task/workers`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    checkResponse(res);
    const { workers } = (await res.json()) as ApiWorkerInfoResponse;
    return workers.map(({ worker_id: workerId, email, status, own }) => ({
      workerId,
      email,
      status,
      own,
    }));
  },
};
