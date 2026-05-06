; sort: read a sequence of bytes and print them in ascending order
;
; Algorithm: bubble sort

(setq arr-base 3000)
(setq count 0)
(setq loaded 0)


(defisr
  (setq val (read))
  (if (!= val 0)
    (progn
      (store-at (+ arr-base count) val)
      (setq count (+ count 1)))
    (setq loaded 1)))


(loop (!= loaded 1) 0)

; Bubble sort
(setq i 0)
(loop (< i (- count 1))
  (progn
    (setq j 0)
    (loop (< j (- (- count 1) i))
      (progn
        (setq a (load (+ arr-base j)))
        (setq b (load (+ arr-base (+ j 1))))
        (if (> a b)
          (progn
            (store-at (+ arr-base j)       b)
            (store-at (+ arr-base (+ j 1)) a)
            0)
          0)
        (setq j (+ j 1))))
    (setq i (+ i 1))))

; Print sorted array
(setq i 0)
(loop (< i count)
  (progn
    (print-int (load (+ arr-base i)))
    (print-char 32)   ; space separator
    (setq i (+ i 1))))

(print-char 10)
