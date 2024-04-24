// @ts-check
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
 * liability, whether in an action of contract, tort or otherwise, arising from,
 * out of or in connection with the software or the use or other dealings in the
 * software.
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the software.
 */

/** @type {<T extends Element> (selector: string) => T} */
export function getElement(selector) {
  const res = document.querySelector(selector);
  if (!res) {
    throw new Error(`Could not find ${selector}`);
  }
  // @ts-ignore Type 'Element' is not assignable to type 'T'.
  return res;
}

/** @type {{ [key: string]: boolean }} */
const isLoading = {};

export function setLoading(
  /** @type {Element} */ element,
  /** @type {boolean} */ value,
) {
  const eId = element.id;
  if (value) {
    isLoading[eId] = true;
    // NOTE: only show loading if an action takes longer than 200ms
    setTimeout(() => {
      if (isLoading[eId]) {
        element.classList.add('loading');
      }
    }, 200);
  } else {
    isLoading[eId] = false;
    // NOTE: never show loading shorter than 200ms which causes blinking
    setTimeout(() => {
      if (!isLoading[eId]) {
        element.classList.remove('loading');
      }
    }, 200);
  }
}
