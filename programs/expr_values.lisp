; expr_values: demonstrate that every form is an expression and produces a value

; (if ...) as expression: value is the taken branch
(print-int (if (= 1 1) 42 0))
(print-char 32)
(print-int (if (= 1 2) 42 0))
(print-char 10)

; (progn ...) as expression: value is the last sub-expression
(print-int (progn
  (setq tmp 5)
  (setq tmp (* tmp tmp))
  tmp))
(print-char 10)

; (loop ...) as expression: value is the last body result
(setq i 1)
(print-int
  (loop (<= i 4)
    (setq i (* i 2))))
(print-char 10)

; (setq ...) as expression: value is the assigned value,
; so assignments can be nested inside other expressions
(print-int (setq x (+ 3 (setq y 7))))
(print-char 32)
(print-int x)
(print-char 32)
(print-int y)
(print-char 10)
