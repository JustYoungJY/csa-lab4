; hello: print "Hello, World!"

(defun print-string (ptr)
  (setq ch (load ptr))
  (loop (!= ch 0)
    (progn
      (print-char ch)
      (setq ptr (+ ptr 1))
      (setq ch (load ptr)))))

(print-string "Hello, World!")
(print-char 10)
