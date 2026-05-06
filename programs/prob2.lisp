; Euler Problem 6: Sum Square Difference
;
; Find the difference between the square of the sum and the sum of squares
; of the first 100 natural numbers
;
; sum_sq = 1^2 + 2^2 + ... + 100^2 = 338350
; sq_sum = (1 + 2 + ... + 100)^2  = 5050^2 = 25502500
; answer = sq_sum - sum_sq = 25164150

(setq n 100)

(setq sum-sq 0)
(setq i 1)
(loop (<= i n)
  (progn
    (setq sum-sq (+ sum-sq (* i i)))
    (setq i (+ i 1))))

(setq s 0)
(setq i 1)
(loop (<= i n)
  (progn
    (setq s (+ s i))
    (setq i (+ i 1))))

(setq sq-sum (* s s))

(print-int (- sq-sum sum-sq))
(print-char 10)
