import styled from 'styled-components';

export const NavButton = styled.button<NavButtonProps>`
  appearance: none;
  display: inline-block;
  text-align: center;
  vertical-align: middle;
  pointer-events: auto;
  cursor: pointer;
  border: 0;
  opacity: 0.8;
  color: var(--button-text-dim);
  border-radius: var(--button-radius);
  width: var(--button-size);
  height: var(--button-size);
  background-color: ${(props) =>
    props.isChecked
      ? 'var(--button-background-lit)'
      : 'var(--button-background)'};

  &:hover {
    background-color: ${(props) =>
      props.isChecked ? 'var(--button-hover-lit)' : 'var(--button-hover)'};
  }
  &:active {
    background-color: ${(props) =>
      props.isChecked ? 'var(--button-active-lit)' : 'var(--button-active)'};
    background-color: var(--button-active);
  }
`;

export const VNavButton = styled(NavButton)<VOverlayProps>`
  display: ${(props) => (props.isVisible ? 'inline-block' : 'none')};
  position: fixed;
  ${(props) => (props.isTop ? 'top' : 'bottom')}: 0;
  right: 0;
`;

export const HOverlay = styled.div<HOverlayProps>`
  height: var(--button-size);
  position: absolute;
  left: 0;
  ${(props) => (props.isTop ? 'top' : 'bottom')}: 0;
  display: ${(props) => (props.isVisible ? 'flex' : 'none')};
  justify-content: space-between;
  flex-direction: ${(props) => (props.forceRight ? 'row-reverse' : 'row')};
  flex-wrap: nowrap;
  width: var(--main-size);
  pointer-events: none;
`;

export const HNavButton = styled(NavButton)``;

export const WMOverlay = styled.div<WMProps>`
  width: var(--button-size);
  height: var(--main-size);
  position: absolute;
  ${(props) => (props.isLeft ? 'left' : 'right')}: 0;
  top: 0;
  display: ${(props) => (props.isVisible ? 'flex' : 'none')};
  justify-content: end;
  flex-direction: column;
  flex-wrap: nowrap;
  pointer-events: none;
`;

export const WriteMessageButton = styled(NavButton)`
  font-size: 1.5em;
`;

type NavButtonProps = {
  isChecked?: boolean;
};

type VOverlayProps = {
  isTop: boolean;
  isVisible: boolean;
};

type HOverlayProps = {
  isTop: boolean;
  isVisible: boolean;
  forceRight?: boolean;
};

type WMProps = {
  isLeft: boolean;
  isVisible: boolean;
};
