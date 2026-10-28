// Income tax by slab, with relief for senior citizens.
import java.util.Scanner;

public class TaxSlab {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);

        System.out.print("Annual income (in thousands): ");
        int income = in.nextInt();
        System.out.print("Age: ");
        int age = in.nextInt();

        if (income < 0 || age < 0) {
            System.out.println("Invalid input");
            return;
        }

        double rate;
        if (income <= 300) {
            rate = 0;
        } else if (income <= 700) {
            rate = 0.05;
        } else if (income <= 1000) {
            rate = 0.10;
        } else if (income <= 1200) {
            rate = 0.15;
        } else {
            rate = 0.20;
        }

        if (age >= 60 && income > 300) {
            rate = rate - 0.05;
            System.out.println("Senior citizen relief");
        }

        System.out.printf("Tax: %.2f%n", income * rate);
    }
}
