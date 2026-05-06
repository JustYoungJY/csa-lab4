; Test 1: 64-bit addition
; A = B = 3 000 000 000
; Sum = 6 000 000 000

(setq a-lo (* 3000 1000000))
(setq a-hi 0)
(setq b-lo (* 3000 1000000))
(setq b-hi 0)

(setq r-lo (+ a-lo b-lo))
(setq r-hi (adc a-hi b-hi))

(print-int64 r-hi r-lo)
(print-char 10)


; Test 2: 64-bit subtraction
; 6 000 000 000 - 3 000 000 000 = 3 000 000 000

(setq s-lo (- r-lo b-lo))
(setq s-hi (sbb r-hi b-hi))

(print-int64 s-hi s-lo)
(print-char 10)


; Test 3: signed 32x32->64 multiply
; 100 000 * 100 000 = 10 000 000 000

(mul64 100000 100000 m-lo m-hi)

(print-int64 m-hi m-lo)
(print-char 10)


; Test 4: negative 32-bit value
; 0 - 5 = -5

(setq neg-val (- 0 5))
(print-int neg-val)
(print-char 10)


; Test 5: signed 32x32->64 multiply with a negative operand
; -100 000 * 100 000 = -10 000 000 000

(mul64 -100000 100000 mn-lo mn-hi)

(print-int64 mn-hi mn-lo)
(print-char 10)
