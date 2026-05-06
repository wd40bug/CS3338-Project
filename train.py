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
from model import SRUModel
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

# extract reddit data
def reddit_extract(files, folder_path, reddit_list, start_index, end_index):
    for file in tqdm(files, desc="Iterating through .parquet files"):
        try:
            file_path = os.path.join(folder_path, file)
            table = pq.read_table(file_path, columns=['body'])
            table = table[start_index:end_index] # take examples from each file for training
            reddit_list.extend(table['body'].to_pylist())
            if len(reddit_list) >= MAX_TOTAL:
                break
        except Exception as e:
            print(f"Error: {e}")
    return reddit_list
        
# extract sms data
def sms_extract(sms_list, filepath):
    with open(filepath, 'r') as file: # for windows
        for line in tqdm(file, desc="Iterating through SMS data"):
            if line.startswith('ham'): # only take real examples, not spam
                line = line[4:]
                sms_list.append(line.strip())
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
        cleaned_text.append(add_FIGS_LTRS(line + '\r\n')) # add FIGS and LTRS tokens to the text
        if len(line) > MAX_LENGTH:
            continue
    cleaned_text = [line for line in cleaned_text if len(line) > 0] # keep lines that aren't empty
    print(f"After cleaning, there are {len(cleaned_text)} examples.")
    
    # Tokenize Text
    
    tokenizer = {char: idx for idx, char in enumerate(RTTY_Chars)} # create tokenizer dictionary to convert characters to integers for model input
    tokenized = [[tokenizer[char] for char in line] for line in cleaned_text] # tokenize the text with the tokenizer dictionary
    return tokenized
    
def shift_augmentation(shift, prob, rng=None): # need rng for validation dataset to apply the same augmentation every time
    # r = torch.rand(1, generator=rng).item() if rng else torch.rand(1).item()
    # if r < prob:
    #     augtype = torch.randint(0, 3, (1,), generator=rng).item() if rng else torch.randint(0, 3, (1,)).item()
    #     if augtype == 1:
    #         return "FIGS" if shift == "LTRS" else "LTRS" # switch shift type
    #     else:
    #         return shift # keep the same shift type
    # return shift # if no augmentation, return original shift token
    r = torch.rand(1, generator=rng).item() if rng else torch.rand(1).item()
    if r < prob:
        return MASK_TOKEN  # apply masking
    return shift  # otherwise, return original shift token

def bit_augmentation(binary, prob, rng=None):
    bits = list(binary) # convert binary string to list for flips
    for i in range(len(bits)): # iterate over list of bits
        if(torch.rand(1, generator=rng).item() if rng else torch.rand(1).item()) < prob: # with probability prob, flip the bit (uniform distribution)
            bits[i] = '1' if bits[i] == '0' else '0' # flip the bit
    return ''.join(bits) # convert list of bits back to string

# Accepts one list (of ints), returns one list (of ints)
bit_prob = 0.10
shift_prob = 0.15
tokenizer = {char: idx for idx, char in enumerate(RTTY_Chars)} # create tokenizer dictionary to convert characters to integers for model input
inv_tokenizer = {idx: char for char, idx in tokenizer.items()} # create inverse tokenizer to convert integers back to characters for augmentation
def augmentation(tokenized, bit_prob, shift_prob, val, index, tokenizer, inv_tokenizer):
    if val:
        rng = torch.Generator()
        rng.manual_seed(index)
    else:
        rng = None
        
    augmented = []
    
    mode = "LTRS"
    
    for token in tokenized:
        if token == PAD_TOKEN:
            augmented.append(token)
            continue
        char = inv_tokenizer[token]
        
        # Shift augmentation
        if char in ["FIGS", "LTRS"]: # skip shift augmentation as a test
            mode = char
            aug_shift = shift_augmentation(char, shift_prob, rng)
            augmented.append(tokenizer.get(aug_shift, token))
            continue
        
        # Convert char to binary for bit flip
        bin_str = CHAR_TO_BIN.get(char)
        if bin_str is None:
            augmented.append(token)
            continue
        
        # Bit flip
        aug_bin = bit_augmentation(bin_str, bit_prob, rng)
        
        # Decode based on mode (LTRS or FIGS)
        if mode == "LTRS":
            aug_char = LTRS_BIN_TO_CHAR.get(aug_bin, char) # Convert back to char, if not found in dictionary (shouldn't happen), keep original char
        else:
            aug_char = FIGS_BIN_TO_CHAR.get(aug_bin, char) # Convert back to char, if not found in dictionary (shouldn't happen), keep original char
            
        aug_token = tokenizer.get(aug_char, token) # Convert char to token 
        augmented.append(aug_token)
        
    return augmented

def collate_fn(batch):
    noisy, clean = zip(*batch) # separate clean and noisy tokenized text
    max_length = MAX_LENGTH
    padded_noisy = [seq[:max_length] + [PAD_TOKEN] * (max_length - len(seq[:max_length])) for seq in noisy] # pad the noisy sequences to max length
    padded_clean = [seq[:max_length] + [PAD_TOKEN] * (max_length - len(seq[:max_length])) for seq in clean] # pad the clean sequences to max length
    return torch.tensor(padded_noisy, dtype=torch.long), torch.tensor(padded_clean, dtype=torch.long) # return the padded sequences as a tuple
    
class CustomDataset(Dataset):
    def __init__(self, txt, augmentation, train, validation, bit_prob, shift_prob, tokenizer, inv_tokenizer):
        self.text = txt
        self.augmentation = augmentation
        self.train = train
        self.validation = validation
        self.bit_prob = bit_prob
        self.shift_prob = shift_prob
        self.tokenizer = tokenizer
        self.inv_tokenizer = inv_tokenizer
    def __len__(self):
        return len(self.text)
    def __getitem__(self, index):
        text = self.text[index]
        if self.train:
            noisy_text = self.augmentation(text, self.bit_prob, self.shift_prob, self.validation, index, self.tokenizer, self.inv_tokenizer)
        elif self.validation:
            noisy_text = self.augmentation(text, self.bit_prob, self.shift_prob, self.validation, index, self.tokenizer, self.inv_tokenizer)
        else:
            noisy_text = text
        return noisy_text, text # input, target pair


def main():
    # Extract and preprocess data
    
    reddit_folder_path = "/home/natep/data/Reddit_Data" # for WSL2
    #reddit_folder_path = "C:\\Users\\natep\\Downloads\\Reddit_Data" # for Windows
    sms_filepath = '/home/natep/data/smsspamcollection.txt' # for WSL2
    #sms_filepath = 'C:\\Users\\natep\\Downloads\\SMS_Data\\smsspamcollection.txt' # for Windows
    reddit_files = [file for file in os.listdir(reddit_folder_path) if file.endswith(".parquet")] # list of .parquet files for reddit data
    reddit_train_list = [] # list to hold reddit training data
    reddit_test_list_0 = [] # lists to hold reddit test data
    sms_list = [] # list to hold sms data, all for training
    
    reddit_train_list = reddit_extract(reddit_files, reddit_folder_path, reddit_train_list, MAX_PER_FILE * 3, MAX_PER_FILE * 4) # Extract data
    reddit_test_list_0 = reddit_extract(reddit_files, reddit_folder_path, reddit_test_list_0, MAX_PER_FILE, 2*MAX_PER_FILE)
    sms_extract(sms_list, sms_filepath)
    
    reddit_train_list = preprocess(reddit_train_list) # Preprocess data
    reddit_test_list_0 = preprocess(reddit_test_list_0)
    sms_list = preprocess(sms_list)
    
    train_list = reddit_train_list + sms_list # combine SMS and Reddit data
    random.seed(50) # set random seed for reproducibility of train/val split
    random.shuffle(train_list)
    random.shuffle(reddit_test_list_0)
    val_list = reddit_test_list_0[:5000] # use first 5000 examples for validation, rest for testing
    reddit_test_list_0 = reddit_test_list_0[5000:20000]
    
    # Model Parameters
    embedding_dim = 144 # try 128 next?
    hidden_dim = 288 # try 256 next?
    dropout = 0.2 # 0.2 had 68.32% test
    num_layers = 3
    bidirectional = True
    
    # Hyperparameters
    batch_size = 144
    num_epochs = 100 # number of iterations for training loop
    learning_rate = 0.0011 # initial learning rate
    weight_decay = 0.00035 # 0.0001 to 0.001
    max_grad = 3.0 # gradient clipping value
    patience = 10 # for early stopping
    bprob_start = 0.05 # augmentation change, was 0.05
    bprob_end = 0.20 # was 0.15
    sprob_start = 0.05
    sprob_end = 0.20
    val_bprob = 0.10
    val_sprob = 0.15
    alpha = 1.3 # from 1.2, higher should be smoother early on
    warmup = 5

    train_ds = CustomDataset(train_list, augmentation, train = True, validation = False,  bit_prob=bprob_start, shift_prob=sprob_start, tokenizer=tokenizer, inv_tokenizer=inv_tokenizer)
    test_ds = CustomDataset(reddit_test_list_0, augmentation, train = False, validation = True, bit_prob=val_bprob, shift_prob=val_sprob, tokenizer=tokenizer, inv_tokenizer=inv_tokenizer)
    val_ds = CustomDataset(val_list, augmentation, train = False, validation = True, bit_prob=val_bprob, shift_prob=val_sprob, tokenizer=tokenizer, inv_tokenizer=inv_tokenizer)
    train_dataloader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_fn, persistent_workers=True, pin_memory=True, num_workers=6, prefetch_factor=4) # create dataloader for training data
    test_dataloader = DataLoader(test_ds, batch_size=batch_size, collate_fn=collate_fn, persistent_workers=True, pin_memory=True, num_workers=1, prefetch_factor=4) # create dataloader for test data
    val_dataloader = DataLoader(val_ds, batch_size=batch_size, collate_fn=collate_fn, persistent_workers=True, pin_memory=True, num_workers=6, prefetch_factor=4) # create dataloader for validation data

    model = SRUModel(vocab_size, embedding_dim=embedding_dim, hidden_dim=hidden_dim, num_layers=num_layers, dropout=dropout, bidirectional=bidirectional) # instantiate model
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer=optimizer, T_max=num_epochs, eta_min=3e-5)
    
    model.to(device) # move model to GPU if available
    
    writer = SummaryWriter(log_dir="runs/sru_model") # for graphing with tensorboard

    count = 0
    best_val_corrupt = 0
    # Training Loop
    for epoch in range(num_epochs):

        if(epoch < warmup):
            current_bit_prob = 0.04 + 0.01 * (epoch / warmup)
            current_shift_prob = 0.04 + 0.01 * (epoch / warmup)
            lambda_denoise = 1.1 + 0.1 * (epoch / warmup)
        else:
            current_bit_prob = min(1, bprob_start + (bprob_end - bprob_start) * ((epoch / 15) ** alpha))
            current_shift_prob = min(1, sprob_start + (sprob_end - sprob_start) * ((epoch / 15) ** alpha))
            lambda_denoise = 1.2 + 0.5 * ((epoch - warmup) / (num_epochs - warmup))

        train_ds.bit_prob = current_bit_prob
        train_ds.shift_prob = current_shift_prob

        epoch_train_loss = 0.0
        epoch_train_acc_all = 0.0
        epoch_train_acc_corrupt = 0.0
        train_batch = 0
        train_tokens = 0

        epoch_val_loss = 0.0
        epoch_val_acc_all = 0.0
        epoch_val_acc_corrupt = 0.0
        val_batch = 0
        val_tokens = 0

        model.train()

        for batch in tqdm(train_dataloader, desc=f"Training Epoch {epoch+1}/{num_epochs}"):

            noisy, clean = batch
            noisy = noisy.to(device, non_blocking=True)
            clean = clean.to(device, non_blocking=True)

            optimizer.zero_grad()

            output = model(noisy)
            preds = torch.argmax(output, dim=2)

            truth = (clean != PAD_TOKEN) & (clean != MASK_TOKEN)
            corrupt = (noisy != clean) & truth

            token_acc_all = ((preds == clean) & truth).sum().float() / truth.sum().clamp_min(1.0)
            token_acc_corrupt = ((preds == clean) & corrupt).sum().float() / corrupt.sum().clamp_min(1.0)

            epoch_train_acc_all += token_acc_all.item()
            epoch_train_acc_corrupt += token_acc_corrupt.item()

            output_flat = output.reshape(-1, vocab_size)
            clean_flat = clean.reshape(-1)

            per_token_loss = F.cross_entropy(output_flat, clean_flat, reduction='none', label_smoothing=0.1)

            truth_flat = truth.reshape(-1).float()
            corrupt_flat = corrupt.reshape(-1).float()

            weights = torch.ones_like(per_token_loss)
            weights = weights * truth_flat
            weights = weights + (lambda_denoise - 1.0) * corrupt_flat

            loss = (per_token_loss * weights).sum() / weights.sum().clamp_min(1.0)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad)
            optimizer.step()

            num_tokens = truth.sum().item()

            epoch_train_loss += loss.item() * num_tokens
            train_tokens += num_tokens
            train_batch += 1

        avg_train_loss = epoch_train_loss / max(train_tokens, 1)
        avg_train_acc_all = epoch_train_acc_all / max(train_batch, 1)
        avg_train_acc_corrupt = epoch_train_acc_corrupt / max(train_batch, 1)

        writer.add_scalar("Loss/Train", avg_train_loss, epoch+1)
        writer.add_scalar("AccAll/Train", avg_train_acc_all, epoch+1)
        writer.add_scalar("AccCorrupt/Train", avg_train_acc_corrupt, epoch+1)

        scheduler.step()
        current_lr = optimizer.param_groups[0]['lr']
        writer.add_scalar("Learning Rate", current_lr, epoch+1)

        model.eval()

        with torch.no_grad():
            for batch in tqdm(val_dataloader, desc=f"Validating Epoch {epoch+1}/{num_epochs}"):

                noisy, clean = batch
                noisy = noisy.to(device, non_blocking=True)
                clean = clean.to(device, non_blocking=True)

                output = model(noisy)
                preds = torch.argmax(output, dim=2)

                truth = (clean != PAD_TOKEN) & (clean != MASK_TOKEN)
                corrupt = (noisy != clean) & truth

                token_acc_all = ((preds == clean) & truth).sum().float() / truth.sum().clamp_min(1.0)
                token_acc_corrupt = ((preds == clean) & corrupt).sum().float() / corrupt.sum().clamp_min(1.0)

                epoch_val_acc_all += token_acc_all.item()
                epoch_val_acc_corrupt += token_acc_corrupt.item()

                output_flat = output.reshape(-1, vocab_size)
                clean_flat = clean.reshape(-1)

                per_token_loss = F.cross_entropy(output_flat, clean_flat, reduction='none')

                truth_flat = truth.reshape(-1).float()
                corrupt_flat = corrupt.reshape(-1).float()

                weights = torch.ones_like(per_token_loss)
                weights = weights * truth_flat
                weights = weights + (lambda_denoise - 1.0) * corrupt_flat

                val_loss = (per_token_loss * weights).sum() / weights.sum().clamp_min(1.0)

                num_tokens = truth.sum().item() 

                epoch_val_loss += val_loss.item() * num_tokens
                val_tokens += num_tokens
                val_batch += 1

        avg_val_loss = epoch_val_loss / max(val_tokens, 1)
        avg_val_acc_all = epoch_val_acc_all / max(val_batch, 1)
        avg_val_acc_corrupt = epoch_val_acc_corrupt / max(val_batch, 1)

        writer.add_scalar("Loss/Validation", avg_val_loss, epoch+1)
        writer.add_scalar("AccAll/Validation", avg_val_acc_all, epoch+1)
        writer.add_scalar("AccCorrupt/Validation", avg_val_acc_corrupt, epoch+1)

        print(
            f"Epoch {epoch+1} | "
            f"Train Loss: {avg_train_loss:.4f} | "
            f"Train All Acc: {avg_train_acc_all:.4f} | "
            f"Train Corr Acc: {avg_train_acc_corrupt:.4f} | "
            f"Val Loss: {avg_val_loss:.4f} | "
            f"Val All Acc: {avg_val_acc_all:.4f} | "
            f"Val Corr Acc: {avg_val_acc_corrupt:.4f}"
        )

        writer.flush()

        if ((avg_val_acc_corrupt > best_val_corrupt) and (epoch > warmup)):
            best_val_corrupt = avg_val_acc_corrupt
            torch.save(model.state_dict(), "best_model.pt")
            count = 0
        else:
            count += 1
            if count >= patience:
                print(f"Early stopping triggered at epoch {epoch+1}.")
                break
            
    writer.close()

    # Testing
    model_path = "best_model.pt"
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)

    correct_test_corrupt = 0
    total_test_corrupt = 0
    correct_test_all = 0
    total_test_all = 0
    test_batch = 0
    total_test_loss = 0
    lambda_denoise = 1.7

    model.eval()
    for batch in tqdm(test_dataloader, desc=f"Testing Model: {model_path}"):
        with torch.no_grad():
            noisy, clean = batch
            noisy = noisy.to(device, non_blocking=True)
            clean = clean.to(device, non_blocking=True)

            output = model(noisy)
            preds = torch.argmax(output, dim=2)

            truth = (clean != PAD_TOKEN) & (clean != MASK_TOKEN)
            corrupt = (noisy != clean) & truth

            correct_test_corrupt += ((preds == clean) & corrupt).sum().item()
            total_test_corrupt += corrupt.sum().clamp_min(1).item()
            correct_test_all += ((preds == clean) & truth).sum().item()
            total_test_all += truth.sum().clamp_min(1).item()

            output_flat = output.reshape(-1, vocab_size)
            clean_flat = clean.reshape(-1)

            per_token_loss = F.cross_entropy(output_flat, clean_flat, reduction='none')

            truth_flat = truth.reshape(-1).float()
            corrupt_flat = corrupt.reshape(-1).float()

            weights = torch.ones_like(per_token_loss)
            weights = weights * truth_flat
            weights = weights + (lambda_denoise - 1.0) * corrupt_flat

            loss = (per_token_loss * weights).sum() / weights.sum().clamp_min(1.0)

            total_test_loss += loss.item()
            test_batch += 1

    avg_test_loss = total_test_loss / max(test_batch, 1)
    avg_test_acc_corrupt = correct_test_corrupt / max(total_test_corrupt, 1)
    avg_test_acc_all = correct_test_all / max(total_test_all, 1)

    print(f"Average Test Loss:         {avg_test_loss:.4f}")
    print(f"Average Test All Acc:      {avg_test_acc_all:.4f}")
    print(f"Average Test Corrupt Acc:  {avg_test_acc_corrupt:.4f}")
    
if __name__ == "__main__":
    main()

