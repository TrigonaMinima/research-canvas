Deep learning research moves fast, and a reader needs to fold away the parts they
already understand to keep the parts still in question in view.

# Sections And Folding

The document carries its own structure now, built straight from the headings a
writer already used to organise the piece, with no extra syntax to learn.

## Background

Transformer models replaced recurrent networks by letting every position attend
to every other position directly, without walking the sequence step by step.

### Recurrent Networks

A recurrent network reads a sequence one token at a time, carrying a hidden state
forward, which makes the steps hard to parallelise across long documents.

#### Vanishing Gradients

Gradients shrink as they are carried back through many steps, so a recurrent
network struggles to learn dependencies that span the whole sequence.

## Background

Attention weighs every position against every other position in one pass, which
parallelises across the whole sequence and removes the distance penalty a
recurrent network pays.
