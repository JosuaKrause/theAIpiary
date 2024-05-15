import { createSlice } from '@reduxjs/toolkit';
import { User } from '../api/types';

type UserState = {
  currentUser: Readonly<User> | undefined;
};

type SetAction = {
  payload: {
    user: Readonly<User> | undefined;
  };
};

type UserReducers = {
  setUser: (state: UserState, action: SetAction) => void;
};

const userStateSlice = createSlice<UserState, UserReducers, string>({
  name: 'userState',
  initialState: {
    currentUser: undefined,
  },
  reducers: {
    setUser: (state, action) => {
      const { user } = action.payload;
      state.currentUser = user;
    },
  },
});

export const { setUser } = userStateSlice.actions;

export default userStateSlice.reducer;
