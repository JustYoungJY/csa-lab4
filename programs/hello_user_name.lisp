; hello_user_name: ask for a name and greet the user
;
; Expected interaction:
;   out: What is your name?
;   in:  Alice\n
;   out: Hello, Alice!

(setq name-buf 3000)
(setq name-len 0)
(setq got-name 0)

(defun print-string (ptr)
  (setq ch (load ptr))
  (loop (!= ch 0)
    (progn
      (print-char ch)
      (setq ptr (+ ptr 1))
      (setq ch (load ptr)))))


(defisr
  (setq c (read))
  (if (= c 10)
    (progn
      (store-at (+ name-buf name-len) 0)  ; null-terminate
      (setq got-name 1))
    (if (!= c 0)
      (progn
        (store-at (+ name-buf name-len) c)
        (setq name-len (+ name-len 1)))
      0)))

(print-string "What is your name?")
(print-char 10)

(loop (!= got-name 1) 0)

(print-string "Hello, ")
(print-string name-buf)
(print-char 33)   ; '!'
(print-char 10)
