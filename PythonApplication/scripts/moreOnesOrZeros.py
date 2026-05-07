import os
from random import Random
import pyarrow.parquet as pq
import pandas as pd
from torch.utils.data import Dataset, DataLoader
import random
import html
import re
from tqdm import tqdm
import torch
from torch.utils.tensorboard import SummaryWriter
import torch.nn.functional as F

unholiness = ["SEX", "PUSSY", "CUM", "VAGINA", "FUCK", "COCK", "DICK", "PENIS", "PEEEEEEEEEENIS", "MOLESTATION", "DOGGY", "BOT", "SPAM", "FAPSOCK", "FUCKING HER", "FUCKING THEM", "FUCKING EVERYONE", "FUCKING HIM", "FAG","FAGS","FAGGOT","FAGGOTS","PORN", "CHILDPORN"]
print(f"How many depraved words or phrases did I see AT LEAST once in this awful data: {len(unholiness)}")

LTRS = ["A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T",
        "U","V","W","X","Y","Z","\r"," ","\n", "FIGS", "LTRS", "<PAD>", "<MASK>"] # LTRS for RTTY transmission

FIGS = ["-","?",":","$","3","!","&","#","8","4","(",")",".",",","9","0","1","\'","5","7",
        ";","2","/","6","\"","\n"," ","\r", "FIGS", "LTRS", "<PAD>", "<MASK>"] # FIGS for RTTY transmission

RTTY_Chars = list(dict.fromkeys(LTRS + FIGS)) # all unique characters in LTRS and FIGS, needed for tokenizer

LTRS_Bin = ["00011","11001","01110","01001","00001","01101","11010","10100","00110","01011","01111","10010","11100","01100","11000","10110","10111",
        "01010","00101","10000","00111","11110","10011","11101","10101","10001","00010","00100","01000","11011", "11111"]

FIGS_Bin = ["00011","11001","01110","01001","00001","01101","11010","10100","00110","01011","01111","10010","11100","01100","11000","10110","10111",
        "01010","10000","00111","11110","10011","11101","10101","10001","00010","00100","01000","11011", "11111"]

LTRS_TO_BIN = {char: b for char, b in zip(LTRS, LTRS_Bin)} # dictionary to convert LTRS characters to binary strings for bit flips
FIGS_TO_BIN = {char: b for char, b in zip(FIGS, FIGS_Bin)} # dictionary to convert FIGS characters to binary strings for bit flips
CHAR_TO_BIN = {**LTRS_TO_BIN, **FIGS_TO_BIN} # combine dictionaries (unpacking) to convert all RTTY characters to binary strings for bit flips
LTRS_BIN_TO_CHAR = {b: char for char, b in zip(LTRS, LTRS_Bin)} # dictionary to convert binary strings back to LTRS characters after bit flips
FIGS_BIN_TO_CHAR = {b: char for char, b in zip(FIGS, FIGS_Bin)} # dictionary to convert binary strings back to FIGS characters after bit flips

vocab_size = len(RTTY_Chars) # useful for data augmentation and model instantiation

MAX_PER_FILE = 7_500 # values for reddit data extraction
MAX_TOTAL = 750_000
MAX_LENGTH = 255
PAD_TOKEN = RTTY_Chars.index("<PAD>") # index for padding token, needed for collate_fn
MASK_TOKEN = RTTY_Chars.index("<MASK>")  # or whatever token you use for masking

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(device)


# extract sms data
def sms_extract(sms_list, filepath):
    with open(filepath, 'r') as file: # for windows
        for line in tqdm(file, desc="Iterating through SMS data"):
            if line.startswith('ham'): # only take real examples, not spam
                line = line[4:]
                sms_list.append(line.strip())

    print(f"Extracted {len(sms_list)} SMS examples.")
    return sms_list

# Accepts list of strings, returns list of strings
def add_FIGS_LTRS(text):
    new_line = []
    mode = "LTRS"
    for char in text:
        if char in LTRS: # iterate through each character, add FIGS or LTRS when switching between character sets
            if mode != "LTRS":
                new_line.append("LTRS")
                mode = "LTRS"
            new_line.append(char)
        elif char in FIGS:
            if mode != "FIGS":
                new_line.append("FIGS")
                mode = "FIGS"
            new_line.append(char)
        else: # skip unknown symbols, shouldn't happen due to preprocessing
            continue

    print(f"Added FIGS and LTRS tokens. Original length: {len(text)}, new length: {len(new_line)}")
    return new_line

def preprocess(text): 
    cleaned_text = []
    
    for line in tqdm(text, desc="Preprocessing and Tokenizing Data"):
        line = html.unescape(line) # Convert HTML tags to normal characters ex) "&gt"
        line = re.sub(r'http\S+', '', line) # Remove links
        line = re.sub(r'[^A-Za-z0-9\-?:$!&#()\.,\';/\"\r\n ]+', ' ', line) # removes all characters except those in FIGS and LTRS
        line = re.sub(r'\s+', ' ', line).strip() # Remove extra whitespace
        line = line.upper() # uppercase everything to match char_set
        if any(word in line for word in unholiness): # skip lines that contain bad words (unholiness list)
            continue
        if line in ["REMOVED", "DELETED"]: # skip lines that just say removed or deleted (reddit data)
            continue
        cleaned_text.append(line) # add FIGS and LTRS tokens to the text
        if len(line) > MAX_LENGTH:
            continue
    cleaned_text = [line for line in cleaned_text if len(line) > 0] # keep lines that aren't empty
    print(f"After cleaning, there are {len(cleaned_text)} examples.")
    
    return cleaned_text
    
sms_list = []
sms_list = sms_extract(sms_list, "PythonApplication/smsspamcollection.txt")

sms_list = preprocess(sms_list)

print(f"Example preprocessed line: {sms_list[9]}")

bin_lines = []

# convert preprocessed text to binary strings
for line in sms_list:
    bin_line = ""
    for char in line:
        if char in RTTY_Chars:
            bin_line += CHAR_TO_BIN[char]
        else:
            continue
    bin_lines.append(bin_line)

# count ones and zeros in the binary strings
total_ones = 0
total_zeros = 0
for line in bin_lines:
    for char in line:
        if char not in RTTY_Chars:
            continue
        else:
            total_ones += char.count('1')
            total_zeros += char.count('0')

print(f"Total ones: {total_ones}")
print(f"Total zeros: {total_zeros}")

print(f"Ratio of zeros to ones: {total_zeros / total_ones:.2f}")