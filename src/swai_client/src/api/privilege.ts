import { URL_PREFIX } from '../misc/constants';
import { json, toJson } from '../misc/util';
import {
  ApiLinkResponse,
  ApiLoginResponse,
  ApiLogout,
  MHash,
  Token,
  Username,
  VoteTypeExt,
} from './types';

export type PrivilegeApiProvider = {
  login: (user: Readonly<Username>) => Promise<ApiLoginResponse>;
  logout: (token: Readonly<Token>) => Promise<ApiLogout>;
  userInfo: (token: Readonly<Token>) => Promise<ApiLoginResponse>;
  vote: (
    token: Readonly<Token>,
    parent: Readonly<MHash>,
    child: Readonly<MHash>,
    votes: Readonly<VoteTypeExt[]>,
    isadd: Readonly<boolean>,
  ) => Promise<ApiLinkResponse>;
  writeMessage: (
    token: Readonly<Token>,
    parent: Readonly<MHash>,
    msg: string,
  ) => Promise<ApiLinkResponse>;
};

export const DEFAULT_PRIVILEGE_API: PrivilegeApiProvider = {
  login: async (user) => {
    return fetch(`${URL_PREFIX}/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: toJson({ user }),
    }).then(json);
  },
  logout: async (token) => {
    return fetch(`${URL_PREFIX}/logout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: toJson({ token }),
    }).then(json);
  },
  userInfo: async (token) => {
    return fetch(`${URL_PREFIX}/user`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: toJson({ token }),
    }).then(json);
  },
  vote: async (token, parent, child, votes, isadd) => {
    return fetch(`${URL_PREFIX}/vote`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: toJson({ token, parent, child, votes, isadd }),
    }).then(json);
  },
  writeMessage: async (token, parent, msg) => {
    return fetch(`${URL_PREFIX}/message`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: toJson({ token, parent, msg }),
    }).then(json);
  },
};
