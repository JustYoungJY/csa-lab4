; loop_demo: demonstrate the (loop) construct and its use as an expression

; Test 1: sum 1..10 = 55

(setq i 1)
(setq sum 0)

(loop (<= i 10)
  (progn
    (setq sum (+ sum i))
    (setq i (+ i 1))))

(print-int sum)
(print-char 10)


; Test 2: loop as an expression: first multiple of 7 greater than 50.
; The loop returns the last value assigned to i, which is 56

(setq i 51)
(setq found
  (loop (!= (mod i 7) 0)
    (setq i (+ i 1))))

(print-int found)
(print-char 10)

; Test 3: nested loops: 3x3 multiplication table
; Expected output: 1  2  3  2  4  6  3  6  9

(setq a 1)
(loop (<= a 3)
  (progn
    (setq b 1)
    (loop (<= b 3)
      (progn
        (print-int (* a b))
        (print-char 32)
        (setq b (+ b 1))))
    (setq a (+ a 1))))

(print-char 10)

; Test 4: binary logarithm: how many times can we halve x before x <= 1?
; x = 64 -> 32 -> 16 -> 8 -> 4 -> 2 -> 1  (6 steps)

(setq x 64)
(setq steps 0)
(loop (> x 1)
  (progn
    (setq x (/ x 2))
    (setq steps (+ steps 1))))

(print-int steps)
(print-char 10)
