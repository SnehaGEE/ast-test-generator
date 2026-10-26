/* Menu-driven bank system: reads choices and values with scanf. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct Transaction {
    char type[20];
    float amount;
    struct Transaction *next;
} Transaction;

typedef struct Account {
    int accNo;
    char name[50];
    float balance;
    Transaction *history;
    struct Account *left, *right;
} Account;

Account *root = NULL;

/* Create a new transaction */
void addTransaction(Account *a, const char *type, float amount) {
    Transaction *t = malloc(sizeof(Transaction));
    if (!t) {
        printf("Memory allocation failed!\n");
        return;
    }

    strcpy(t->type, type);
    t->amount = amount;
    t->next = a->history;
    a->history = t;
}

/* Search account using BST */
Account *search(Account *r, int no) {
    if (r == NULL || r->accNo == no)
        return r;

    if (no < r->accNo)
        return search(r->left, no);

    return search(r->right, no);
}

/* Insert account into BST */
Account *createAccount(Account *r, int no,
                       const char *name, float initial) {
    if (r == NULL) {
        Account *a = calloc(1, sizeof(Account));
        if (!a) {
            printf("Memory allocation failed!\n");
            exit(EXIT_FAILURE);
        }

        a->accNo = no;
        snprintf(a->name, sizeof(a->name), "%s", name);
        a->balance = initial;
        addTransaction(a, "OPEN", initial);
        return a;
    }

    if (no < r->accNo)
        r->left = createAccount(r->left, no, name, initial);
    else if (no > r->accNo)
        r->right = createAccount(r->right, no, name, initial);
    else
        printf("Account number already exists!\n");

    return r;
}

/* Deposit money */
void deposit(int no, float amount) {
    Account *a = search(root, no);

    if (!a) {
        printf("Account not found!\n");
        return;
    }

    if (amount <= 0) {
        printf("Invalid amount!\n");
        return;
    }

    a->balance += amount;
    addTransaction(a, "DEPOSIT", amount);
    printf("Deposit successful. Balance: %.2f\n", a->balance);
}

/* Withdraw money */
void withdraw(int no, float amount) {
    Account *a = search(root, no);

    if (!a) {
        printf("Account not found!\n");
        return;
    }

    if (amount <= 0 || amount > a->balance) {
        printf("Invalid amount or insufficient balance!\n");
        return;
    }

    a->balance -= amount;
    addTransaction(a, "WITHDRAW", amount);
    printf("Withdrawal successful. Balance: %.2f\n", a->balance);
}

/* Display accounts in sorted order */
void displayAccounts(Account *r) {
    if (r == NULL) return;

    displayAccounts(r->left);
    printf("%d | %-20s | %.2f\n",
           r->accNo, r->name, r->balance);
    displayAccounts(r->right);
}

/* Display transaction history */
void showHistory(int no) {
    Account *a = search(root, no);

    if (!a) {
        printf("Account not found!\n");
        return;
    }

    printf("\nTransaction history for %s:\n", a->name);

    for (Transaction *t = a->history; t; t = t->next)
        printf("%-10s : %.2f\n", t->type, t->amount);
}

/* Save accounts to a text file */
void saveAccounts(Account *r, FILE *fp) {
    if (!r) return;

    saveAccounts(r->left, fp);
    fprintf(fp, "%d|%s|%.2f\n",
            r->accNo, r->name, r->balance);
    saveAccounts(r->right, fp);
}

/* Free allocated memory */
void freeAccounts(Account *r) {
    if (!r) return;

    freeAccounts(r->left);
    freeAccounts(r->right);

    Transaction *t = r->history;
    while (t) {
        Transaction *next = t->next;
        free(t);
        t = next;
    }

    free(r);
}

int main(void) {
    int choice, no;
    char name[50];
    float amount;

    do {
        printf("\n===== BANK MANAGEMENT SYSTEM =====\n");
        printf("1. Create Account\n");
        printf("2. Deposit\n");
        printf("3. Withdraw\n");
        printf("4. Check Balance\n");
        printf("5. Display All Accounts\n");
        printf("6. Transaction History\n");
        printf("7. Save Accounts\n");
        printf("0. Exit\n");
        printf("Enter choice: ");

        if (scanf("%d", &choice) != 1) {
            printf("Invalid input!\n");
            break;
        }

        switch (choice) {
        case 1: {
            printf("Account number: ");
            scanf("%d", &no);

            if (search(root, no)) {
                printf("Account number already exists!\n");
                break;
            }

            printf("Account holder name: ");
            scanf(" %49[^\n]", name);

            printf("Initial deposit: ");
            if (scanf("%f", &amount) != 1 || amount < 0) {
                printf("Invalid amount!\n");
                break;
            }

            root = createAccount(root, no, name, amount);
            printf("Account created successfully!\n");
            break;
        }

        case 2:
            printf("Account number and amount: ");
            if (scanf("%d %f", &no, &amount) == 2)
                deposit(no, amount);
            else
                printf("Invalid input!\n");
            break;

        case 3:
            printf("Account number and amount: ");
            if (scanf("%d %f", &no, &amount) == 2)
                withdraw(no, amount);
            else
                printf("Invalid input!\n");
            break;

        case 4: {
            printf("Account number: ");
            if (scanf("%d", &no) != 1) {
                printf("Invalid input!\n");
                break;
            }

            Account *a = search(root, no);
            if (a)
                printf("Balance: %.2f\n", a->balance);
            else
                printf("Account not found!\n");
            break;
        }

        case 5:
            printf("\nAccount No | Name                 | Balance\n");
            displayAccounts(root);
            break;

        case 6:
            printf("Account number: ");
            if (scanf("%d", &no) == 1)
                showHistory(no);
            else
                printf("Invalid input!\n");
            break;

        case 7: {
            FILE *fp = fopen("accounts.txt", "w");
            if (!fp) {
                printf("Could not open file!\n");
                break;
            }

            saveAccounts(root, fp);
            fclose(fp);
            printf("Accounts saved to accounts.txt\n");
            break;
        }

        case 0:
            printf("Exiting...\n");
            break;

        default:
            printf("Invalid choice!\n");
        }
    } while (choice != 0);

    freeAccounts(root);
    return 0;
}
