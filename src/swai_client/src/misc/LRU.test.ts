import LRU from './LRU';

test('LRU manipulations', () => {
  const lru: LRU<string, number> = new LRU(5);
  expect(lru.get('a')).toBe(undefined);
  expect(lru.get('b')).toBe(undefined);
  expect(lru.keys()).toEqual([]);
  expect(lru.values()).toEqual([]);
  lru.set('a', 5);
  expect(lru.get('b')).toBe(undefined);
  expect(lru.keys()).toEqual(['a']);
  expect(lru.values()).toEqual([5]);
  expect(lru.get('a')).toBe(5);
  expect(lru.keys()).toEqual(['a']);
  expect(lru.values()).toEqual([5]);
  lru.set('b', 6);
  expect(lru.keys()).toEqual(['b', 'a']);
  expect(lru.values()).toEqual([6, 5]);
  expect(lru.get('b')).toBe(6);
  expect(lru.keys()).toEqual(['b', 'a']);
  expect(lru.values()).toEqual([6, 5]);
  lru.set('c', 7);
  expect(lru.keys()).toEqual(['c', 'b', 'a']);
  expect(lru.values()).toEqual([7, 6, 5]);
  expect(lru.get('b')).toBe(6);
  expect(lru.keys()).toEqual(['b', 'c', 'a']);
  expect(lru.values()).toEqual([6, 7, 5]);
  lru.set('d', 8);
  lru.set('e', 9);
  expect(lru.keys()).toEqual(['e', 'd', 'b', 'c', 'a']);
  expect(lru.values()).toEqual([9, 8, 6, 7, 5]);
  expect(lru.get('c')).toBe(7);
  expect(lru.keys()).toEqual(['c', 'e', 'd', 'b', 'a']);
  expect(lru.values()).toEqual([7, 9, 8, 6, 5]);
  expect(lru.get('c')).toBe(7);
  expect(lru.keys()).toEqual(['c', 'e', 'd', 'b', 'a']);
  expect(lru.values()).toEqual([7, 9, 8, 6, 5]);
  expect(lru.get('a')).toBe(5);
  expect(lru.keys()).toEqual(['a', 'c', 'e', 'd', 'b']);
  expect(lru.values()).toEqual([5, 7, 9, 8, 6]);
  expect(lru.get('c')).toBe(7);
  expect(lru.keys()).toEqual(['c', 'a', 'e', 'd', 'b']);
  expect(lru.values()).toEqual([7, 5, 9, 8, 6]);

  expect(lru.set('f', 12)).toBe(undefined);
  expect(lru.keys()).toEqual(['f', 'c', 'a', 'e', 'd']);
  expect(lru.values()).toEqual([12, 7, 5, 9, 8]);
  expect(lru.set('f', 10)).toBe(12);
  expect(lru.keys()).toEqual(['f', 'c', 'a', 'e', 'd']);
  expect(lru.values()).toEqual([10, 7, 5, 9, 8]);
  expect(lru.get('d')).toBe(8);
  expect(lru.keys()).toEqual(['d', 'f', 'c', 'a', 'e']);
  expect(lru.values()).toEqual([8, 10, 7, 5, 9]);
  lru.set('g', 11);
  expect(lru.keys()).toEqual(['g', 'd', 'f', 'c', 'a']);
  expect(lru.values()).toEqual([11, 8, 10, 7, 5]);
  expect(lru.get('b')).toBe(undefined);
  expect(lru.get('e')).toBe(undefined);
  expect(lru.get('g')).toBe(11);
  expect(lru.keys()).toEqual(['g', 'd', 'f', 'c', 'a']);
  expect(lru.values()).toEqual([11, 8, 10, 7, 5]);

  expect(lru.has('f')).toBe(true);
  expect(lru.keys()).toEqual(['g', 'd', 'f', 'c', 'a']);
  expect(lru.values()).toEqual([11, 8, 10, 7, 5]);
  expect(lru.has('e')).toBe(false);
  expect(lru.keys()).toEqual(['g', 'd', 'f', 'c', 'a']);
  expect(lru.values()).toEqual([11, 8, 10, 7, 5]);
  lru.delete('f');
  expect(lru.has('f')).toBe(false);
  expect(lru.keys()).toEqual(['g', 'd', 'c', 'a']);
  expect(lru.values()).toEqual([11, 8, 7, 5]);
  lru.set('h', 12);
  expect(lru.keys()).toEqual(['h', 'g', 'd', 'c', 'a']);
  expect(lru.values()).toEqual([12, 11, 8, 7, 5]);
  lru.delete('h');
  expect(lru.keys()).toEqual(['g', 'd', 'c', 'a']);
  expect(lru.values()).toEqual([11, 8, 7, 5]);
  lru.delete('a');
  expect(lru.keys()).toEqual(['g', 'd', 'c']);
  expect(lru.values()).toEqual([11, 8, 7]);
  expect(lru.has('a')).toBe(false);
  lru.delete('a');
  expect(lru.keys()).toEqual(['g', 'd', 'c']);
  expect(lru.values()).toEqual([11, 8, 7]);
  expect(lru.has('a')).toBe(false);
  expect(lru.has('d')).toBe(true);
  lru.delete('d');
  lru.delete('g');
  lru.delete('c');
  expect(lru.keys()).toEqual([]);
  expect(lru.values()).toEqual([]);
});

type Complex = { re: number; im: number };

test('complex keys', () => {
  const lru: LRU<Complex, number> = new LRU(5);
  expect(lru.get({ re: 1, im: -1 })).toBe(undefined);
  expect(lru.get({ im: 0, re: 2 })).toBe(undefined);
  expect(lru.keys()).toEqual([]);
  expect(lru.values()).toEqual([]);
  lru.set({ re: 1, im: -1 }, 1);
  lru.set({ re: 2, im: 0 }, 2);
  lru.set({ im: -1, re: 1 }, 3);
  lru.set({ im: 3, re: 5 }, 4);
  lru.set({ re: 0, im: 1 }, 5);
  lru.set({ re: 4, im: 0 }, 6);
  lru.set({ re: -1, im: -1 }, 7);
  expect(lru.get({ re: 1, im: -1 })).toBe(3);
  expect(lru.get({ im: -1, re: 1 })).toBe(3);
  expect(lru.get({ im: 0, re: 2 })).toBe(undefined);
  expect(lru.get({ re: 2, im: 0 })).toBe(undefined);
  expect(lru.keys()).toEqual([
    { re: 1, im: -1 },
    { re: -1, im: -1 },
    { re: 4, im: 0 },
    { re: 0, im: 1 },
    { re: 5, im: 3 },
  ]);
  expect(lru.values()).toEqual([3, 7, 6, 5, 4]);
  expect(lru.get({ re: -1, im: -1 })).toBe(7);
  expect(lru.get({ im: -1, re: -1 })).toBe(7);
  expect(lru.get({ re: 5, im: 3 })).toBe(4);
  expect(lru.get({ im: 3, re: 5 })).toBe(4);
});
