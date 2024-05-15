import { createSlice } from '@reduxjs/toolkit';

export enum ActiveModal {
  None = 'None',
  Login = 'Login',
}

type ModalState = {
  activeModal: Readonly<ActiveModal>;
};

type SetModal = {
  payload: {
    activeModal: Readonly<ActiveModal>;
  };
};

type ModalReducers = {
  setModal: (state: ModalState, action: SetModal) => void;
};

const modalStateSlice = createSlice<ModalState, ModalReducers, string>({
  name: 'modalState',
  initialState: {
    activeModal: ActiveModal.None,
  },
  reducers: {
    setModal: (state, action) => {
      const { activeModal } = action.payload;
      state.activeModal = activeModal;
    },
  },
});

export const { setModal } = modalStateSlice.actions;

export default modalStateSlice.reducer;
