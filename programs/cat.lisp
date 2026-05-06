; cat: echo every input byte to output

(defisr
  (setq c (read))
  (if (!= c 0)
    (print-char c)
    (halt)))

(loop 1 0)
