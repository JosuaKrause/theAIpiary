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
import { URL_PREFIX } from '../misc/constants';
import {
  ApiChangeCapability,
  ApiChatSessionsResponse,
  ApiLoginResponse,
  ApiPasswordResetTokenResponse,
  ApiUserCapability,
  ApiUserListResponse,
  ApiWorkerInfoResponse,
  ApiWorkerTokenResponse,
  DisplayName,
  LoginInfo,
  Password,
  ResetToken,
  SessionInfo,
  User,
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
  ) => Promise<void>;
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
    (await res.json()) as ApiChangeCapability; // TODO: maybe do something
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
    return users.map(({ email, display_name, capabilities }) => ({
      email,
      displayName: display_name,
      capabilities: toUserCapabilities(capabilities),
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
