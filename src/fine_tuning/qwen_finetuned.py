# -*- coding: utf-8 -*-
"""Qwen_finetuned.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1RqQew2uW2ZC3x_hIXphb-rtepWbUSEZS
"""

pip install transformers datasets peft bitsandbytes accelerate

import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from huggingface_hub import login

hf_token = "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"
login(token=hf_token)

# Step 2: Load Pre-trained Model with 4-bit Quantization
model_name = "Qwen/Qwen2.5-3B-Instruct"
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    load_in_4bit=True,
    device_map="auto",
    torch_dtype=torch.float16,
    trust_remote_code=True
)

# Prepare the model for LoRA fine-tuning
model = prepare_model_for_kbit_training(model)

for name, module in model.named_modules():
    print(name)

from peft import LoraConfig, get_peft_model

# LoRA configuration targeting 'q_proj' and 'v_proj' layers
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,  # scaling factor
    target_modules=["self_attn.q_proj", "self_attn.v_proj"],  #
    lora_dropout=0.1,
    bias="none",
    task_type="CAUSAL_LM"
)

# Apply the LoRA configuration to the model
model = get_peft_model(model, lora_config)

# Step 4: Load Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)

# Step 5: Load and Preprocess the Dataset
dataset = load_dataset("gbharti/wealth-alpaca_lora")

def preprocess_function(examples):
    # Combine instruction and input into a single prompt
    inputs = [f"Instruction: {instruction}\nInput: {input_text}\n" for instruction, input_text in zip(examples['instruction'], examples['input'])]
    model_inputs = tokenizer(inputs, max_length=512, truncation=True, padding="max_length")

    # Tokenize the outputs as labels
    labels = tokenizer(examples['output'], max_length=512, truncation=True, padding="max_length")
    model_inputs["labels"] = labels["input_ids"]
    return model_inputs

tokenized_dataset = dataset.map(preprocess_function, batched=True, remove_columns=dataset["train"].column_names)

# Step 6: Define Training Arguments
from transformers import TrainingArguments
training_args = TrainingArguments(
    output_dir="./results",
    evaluation_strategy="epoch",
    learning_rate=1e-4,
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,
    num_train_epochs=1,
    save_steps=100,
    save_total_limit=2,
    fp16=True,
    logging_dir='./logs',
    logging_steps=10,
    report_to="none",  # Disable reporting to external services
)

# Load the dataset and create a validation split
from transformers import Trainer

dataset = load_dataset("gbharti/wealth-alpaca_lora")
dataset = dataset["train"].train_test_split(test_size=0.1)

# Tokenize the dataset
tokenized_dataset = dataset.map(preprocess_function, batched=True, remove_columns=dataset["train"].column_names)

# Define the Trainer with the new splits
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    eval_dataset=tokenized_dataset["test"]  # Use "test" as validation set
)

# Step 8: Train the Model with LoRA and Quantization
trainer.train()

# Step 9: Save the Fine-Tuned Model and Tokenizer
model.save_pretrained("./fine-tuned-qwen2.5-3b-instruct-lora")
tokenizer.save_pretrained("./fine-tuned-qwen2.5-3b-instruct-lora")

from transformers import AutoModelForCausalLM, AutoTokenizer
from huggingface_hub import HfApi, HfFolder

# Function to push uploaded/trained models to Hugging Face Hub
def save_uploaded_model_to_huggingface_hub(model_path, tokenizer_path, repo_name, username):
    """
    Save an uploaded or trained model to Hugging Face Hub.

    Args:
        model_path (str): Path to the model directory.
        tokenizer_path (str): Path to the tokenizer directory.
        repo_name (str): Repository name on Hugging Face Hub.
        username (str): Hugging Face username.
    """
    # Load the model and tokenizer from the local directory
    model = AutoModelForCausalLM.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)

    # Push the model to Hugging Face Hub
    model.push_to_hub(f"{username}/{repo_name}", use_auth_token=True)
    print(f"Model pushed to Hugging Face Hub at: https://huggingface.co/{username}/{repo_name}")

    # Push the tokenizer to Hugging Face Hub
    tokenizer.push_to_hub(f"{username}/{repo_name}", use_auth_token=True)
    print(f"Tokenizer pushed to Hugging Face Hub at: https://huggingface.co/{username}/{repo_name}")


# Example Usage
if __name__ == "__main__":
    # Define paths and repository information
    model_path = "./path_to_your_model"  # Replace with the path to your saved model
    tokenizer_path = "./path_to_your_model"  # Replace with the path to your saved tokenizer
    repo_name = "your_model_repo_name"  # Replace with your desired repo name on Hugging Face
    username = "your_username"  # Replace with your Hugging Face username

    # Call the function to save the model
    save_uploaded_model_to_huggingface_hub(model_path, tokenizer_path, repo_name, username)

# Step 10: Inference with the Fine-Tuned Model
from transformers import pipeline

# Load the fine-tuned model and tokenizer
fine_tuned_model = AutoModelForCausalLM.from_pretrained("./fine-tuned-qwen2.5-3b-instruct-lora")
fine_tuned_tokenizer = AutoTokenizer.from_pretrained("./fine-tuned-qwen2.5-3b-instruct-lora")

# Initialize the text generation pipeline
generator = pipeline("text-generation", model=fine_tuned_model, tokenizer=fine_tuned_tokenizer)

# Generate a response for a test prompt
prompt = "Explain Stock Market to me"
response = generator(prompt, max_length=1000, num_return_sequences=1)
print(response[0]['generated_text'])

!zip -r fine_tuned_model.zip ./fine-tuned-qwen2.5-3b-instruct-lora