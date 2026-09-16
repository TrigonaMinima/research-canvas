# Attention Is All You Need

The dominant sequence transduction models are based on complex recurrent or
convolutional neural networks that include an encoder and a decoder. We propose a
new simple network architecture, the Transformer, based solely on attention
mechanisms, dispensing with recurrence and convolutions entirely.

## Model Architecture

Most competitive neural sequence transduction models have an encoder-decoder
structure. The encoder maps an input sequence of symbol representations to a
sequence of continuous representations. Given these, the decoder then generates an
output sequence of symbols one element at a time.

We employ a **residual connection** around each of the two sub-layers, followed by
layer normalisation. That is, the output of each sub-layer is
`LayerNorm(x + Sublayer(x))`, where `Sublayer(x)` is the function implemented by
the sub-layer itself.

## Why Self-Attention

Self-attention layers are faster than recurrent layers when the sequence length is
smaller than the representation dimensionality, which is most often the case with
sentence representations used by state-of-the-art models in machine translation.
