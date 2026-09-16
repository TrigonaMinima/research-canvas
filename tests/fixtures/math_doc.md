# Formulas on the Canvas

Einstein's mass-energy relation is written $E = mc^2$, and it says that mass and
energy are two readings of one quantity.

Scaled dot-product attention divides by $\mathrm{Divisor}(d_k)$ before the softmax,
which keeps the gradients from vanishing as the dimensionality grows.

The whole operation is written as one display:

$$\mathrm{Attention}(Q, K, V) = \mathrm{softmax}(QK^T) V$$

A residual connection and a layer normalisation follow, in that order:

\begin{align}
y &= x + \mathrm{Sublayer}(x) \\
z &= \mathrm{LayerNorm}(y)
\end{align}

Prices are not mathematics. It costs $5 and $10 to rent the machine that runs these
examples, and no formula belongs in that sentence.
