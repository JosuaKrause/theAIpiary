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
import {
  ApiUserCapability,
  DisplayName,
  toCapabilityList,
  toUserCapabilities,
  UserEmail,
} from './types';

const ALL_CAPABILITIES: ApiUserCapability[] = [
  'change_capabilities',
  'change_email',
  'create_user',
  'delete_user',
  'list_users',
  'logout_other_user',
  'register_other_worker',
  'register_own_worker',
];

test('capabilities round trip', () => {
  ALL_CAPABILITIES.forEach((cap) => {
    const user = {
      email: 'a@example.com' as UserEmail,
      displayName: 'A' as DisplayName,
      capabilities: toUserCapabilities([cap]),
      isAdmin: false,
    };
    const list = toCapabilityList(user);
    // every capability is listed, exactly the given one is set
    expect(list.map(({ name }) => name).sort()).toEqual(ALL_CAPABILITIES);
    expect(list.filter(({ has }) => has).map(({ name }) => name)).toEqual([
      cap,
    ]);
  });
});
